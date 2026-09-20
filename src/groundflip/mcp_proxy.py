"""Transparent MCP stdio relay with cassette capture and result intervention."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .cassette import CassetteRecorder, InterventionEngine

DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024


class ProxyError(Exception):
    pass


@dataclass(frozen=True)
class ProxyResult:
    exit_code: int
    cassette_path: str
    frames: int
    tool_calls: int


class _InputPump:
    """Daemon reader avoids unsupported add_reader and stuck executor shutdown on Windows."""

    def __init__(self, source: BinaryIO, loop: asyncio.AbstractEventLoop) -> None:
        self.source = source
        self.loop = loop
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True, name="groundflip-stdin")

    def _run(self) -> None:
        try:
            while True:
                line = self.source.readline()
                if not line:
                    self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
                    return
                if isinstance(line, str):
                    line = line.encode("utf-8")
                self.loop.call_soon_threadsafe(self.queue.put_nowait, line)
        except Exception:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)

    def start(self) -> None:
        self.thread.start()


def _parse_line(line: bytes) -> Any | None:
    try:
        return json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _serialize_like(message: Any, original: bytes) -> bytes:
    eol = b"\r\n" if original.endswith(b"\r\n") else b"\n" if original.endswith(b"\n") else b""
    return (
        json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        + eol
    )


def _write_binary(stream: BinaryIO, data: bytes) -> None:
    stream.write(data)
    stream.flush()


async def _stop_child(child: asyncio.subprocess.Process, timeout: float = 3.0) -> None:
    if child.returncode is not None:
        return
    child.terminate()
    try:
        await asyncio.wait_for(child.wait(), timeout=timeout)
    except TimeoutError:
        child.kill()
        await asyncio.wait_for(child.wait(), timeout=timeout)


async def run_proxy(
    upstream_argv: Sequence[str],
    cassette_path: str | Path,
    intervention_path: str | Path | None = None,
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    stderr: BinaryIO | None = None,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> ProxyResult:
    if not upstream_argv:
        raise ProxyError("upstream command is empty")
    if max_frame_bytes < 1024:
        raise ProxyError("max_frame_bytes must be at least 1024")
    source = stdin or sys.stdin.buffer
    destination = stdout or sys.stdout.buffer
    diagnostics = stderr or sys.stderr.buffer
    recorder = CassetteRecorder(
        upstream_argv,
        metadata={
            "intervention_file": bool(intervention_path),
            "max_frame_bytes": max_frame_bytes,
        },
    )
    interventions = InterventionEngine.from_file(intervention_path)
    child: asyncio.subprocess.Process | None = None
    proxy_error: str | None = None
    exit_code = 1
    tasks: list[asyncio.Task[Any]] = []

    try:
        child_env = dict(os.environ)
        if env:
            child_env.update(env)
        child = await asyncio.create_subprocess_exec(
            *upstream_argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=child_env,
            limit=max_frame_bytes + 1,
        )
        assert child.stdin is not None and child.stdout is not None and child.stderr is not None
        loop = asyncio.get_running_loop()
        pump = _InputPump(source, loop)
        pump.start()

        async def relay_client() -> None:
            try:
                while True:
                    line = await pump.queue.get()
                    if line is None:
                        break
                    if len(line) > max_frame_bytes:
                        raise ProxyError(f"client frame exceeds max_frame_bytes={max_frame_bytes}")
                    sequence, message = recorder.record_frame("client_to_server", line)
                    recorder.begin_tool_call(sequence, message)
                    child.stdin.write(line)
                    await child.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                return
            finally:
                with contextlib.suppress(Exception):
                    child.stdin.close()
                    await child.stdin.wait_closed()

        async def relay_server() -> None:
            while True:
                try:
                    line = await child.stdout.readline()
                except ValueError as exc:
                    raise ProxyError(
                        f"server frame exceeds max_frame_bytes={max_frame_bytes}"
                    ) from exc
                if not line:
                    return
                if len(line) > max_frame_bytes:
                    raise ProxyError(f"server frame exceeds max_frame_bytes={max_frame_bytes}")
                message = _parse_line(line)
                pending = recorder.matching_pending(message)
                events: list[dict[str, Any]] = []
                outgoing = line
                if pending is not None:
                    altered, events = interventions.apply_response(
                        tool_name=pending.tool_name,
                        arguments=pending.arguments,
                        request_id=pending.request_id,
                        response=message,
                    )
                    if any(event.get("status") == "replaced" for event in events):
                        outgoing = _serialize_like(altered, line)
                        message = altered
                sequence, recorded_message = recorder.record_frame("server_to_client", outgoing)
                if pending is not None:
                    recorder.finish_tool_call(
                        sequence,
                        recorded_message if recorded_message is not None else message,
                        pending,
                        events,
                    )
                _write_binary(destination, outgoing)

        async def relay_stderr() -> None:
            while True:
                chunk = await child.stderr.read(65536)
                if not chunk:
                    return
                _write_binary(diagnostics, chunk)

        client_task = asyncio.create_task(relay_client(), name="groundflip-client-relay")
        server_task = asyncio.create_task(relay_server(), name="groundflip-server-relay")
        stderr_task = asyncio.create_task(relay_stderr(), name="groundflip-stderr-relay")
        wait_task = asyncio.create_task(child.wait(), name="groundflip-child-wait")
        tasks = [client_task, server_task, stderr_task, wait_task]
        monitored = set(tasks)

        while not wait_task.done():
            done, _ = await asyncio.wait(monitored, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task is wait_task:
                    break
                exception = task.exception()
                if exception is not None:
                    raise exception
                monitored.discard(task)
            if server_task.done() and not wait_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(wait_task), timeout=3)
                except TimeoutError as exc:
                    raise ProxyError("upstream closed stdout without exiting") from exc

        exit_code = wait_task.result()
        client_task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(client_task, server_task, stderr_task, return_exceptions=True),
                timeout=5,
            )
        except TimeoutError:
            for task in (client_task, server_task, stderr_task):
                task.cancel()
            await asyncio.gather(client_task, server_task, stderr_task, return_exceptions=True)
    except Exception as exc:
        proxy_error = f"{type(exc).__name__}: {exc}"
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if child is not None:
            with contextlib.suppress(Exception):
                await _stop_child(child)
        raise
    finally:
        document = recorder.write(cassette_path, exit_code=exit_code, proxy_error=proxy_error)

    return ProxyResult(
        exit_code=exit_code,
        cassette_path=str(Path(cassette_path)),
        frames=len(document["frames"]),
        tool_calls=len(document["calls"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="groundflip-proxy")
    parser.add_argument("--cassette", required=True)
    parser.add_argument("--intervention", "--interventions", dest="intervention")
    parser.add_argument("--cwd")
    parser.add_argument("--max-frame-bytes", type=int, default=DEFAULT_MAX_FRAME_BYTES)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("groundflip-proxy: missing command after --", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(
            run_proxy(
                command,
                args.cassette,
                args.intervention,
                cwd=args.cwd,
                max_frame_bytes=args.max_frame_bytes,
            )
        )
        return result.exit_code
    except Exception as exc:
        print(f"groundflip-proxy: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
