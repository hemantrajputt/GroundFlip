"""Loss-aware, redacted MCP JSON-RPC cassette recording and interventions."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .store import canonical_json, redact

CASSETTE_SCHEMA = "groundflip.cassette/v1"
INTERVENTION_SCHEMA = "groundflip.interventions/v1"


class CassetteError(Exception):
    pass


class CassetteIntegrityError(CassetteError):
    pass


class CassetteInterventionError(CassetteError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _cassette_digest(document: Mapping[str, Any]) -> str:
    body = {key: value for key, value in document.items() if key != "cassette_sha256"}
    return _sha256_text(canonical_json(body))


def _safe_raw(raw: bytes | str) -> tuple[str, Any | None, bool]:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    eol = "\r\n" if text.endswith("\r\n") else "\n" if text.endswith("\n") else ""
    body = text[: -len(eol)] if eol else text
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        safe_text = str(redact(body))
        return safe_text + eol, None, safe_text != body
    safe_message = redact(message)
    changed = safe_message != message
    if changed:
        return canonical_json(safe_message) + eol, safe_message, True
    return text, message, False


def canonical_request_id(value: Any) -> str:
    if value is None:
        return "null:null"
    if isinstance(value, bool):
        return f"bool:{str(value).lower()}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, float):
        return f"float:{value!r}"
    if isinstance(value, str):
        return "str:" + value
    return f"{type(value).__name__}:{canonical_json(value)}"


@dataclass
class PendingToolCall:
    key: str
    call_index: int
    request_id: Any
    tool_name: str
    arguments: Any
    started_monotonic: float = field(default_factory=time.monotonic)


class CassetteRecorder:
    def __init__(self, argv: Iterable[str], metadata: Mapping[str, Any] | None = None) -> None:
        self.started_at = datetime.now(UTC).isoformat()
        self.argv = [redact(str(item)) for item in argv]
        self.metadata = redact(dict(metadata or {}))
        self.frames: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.pending: dict[str, PendingToolCall] = {}

    def record_frame(self, direction: str, raw: bytes | str) -> tuple[int, Any | None]:
        if direction not in {"client_to_server", "server_to_client"}:
            raise CassetteError(f"Invalid frame direction: {direction}")
        safe_raw, message, was_redacted = _safe_raw(raw)
        sequence = len(self.frames)
        frame = {
            "sequence": sequence,
            "direction": direction,
            "at": datetime.now(UTC).isoformat(),
            "raw": safe_raw,
            "raw_sha256": _sha256_text(safe_raw),
            "message": message,
            "message_sha256": _sha256_text(canonical_json(message))
            if message is not None
            else None,
            "redacted": was_redacted,
        }
        self.frames.append(frame)
        return sequence, message

    def begin_tool_call(self, frame_index: int, message: Any) -> PendingToolCall | None:
        if not isinstance(message, Mapping) or message.get("method") != "tools/call":
            return None
        if "id" not in message:
            return None
        params = message.get("params")
        if not isinstance(params, Mapping) or not isinstance(params.get("name"), str):
            return None
        key = canonical_request_id(message["id"])
        call = {
            "call_index": len(self.calls),
            "request_id": redact(message["id"]),
            "tool_name": params["name"],
            "arguments": redact(params.get("arguments", {})),
            "request_frame": frame_index,
            "response_frame": None,
            "request": redact(message),
            "response": None,
            "status": "pending",
            "latency_ms": None,
            "interventions": [],
        }
        self.calls.append(call)
        pending = PendingToolCall(
            key=key,
            call_index=call["call_index"],
            request_id=message["id"],
            tool_name=params["name"],
            arguments=params.get("arguments", {}),
        )
        self.pending[key] = pending
        return pending

    def matching_pending(self, message: Any) -> PendingToolCall | None:
        if not isinstance(message, Mapping) or "id" not in message:
            return None
        return self.pending.get(canonical_request_id(message["id"]))

    def finish_tool_call(
        self,
        frame_index: int,
        message: Any,
        pending: PendingToolCall,
        interventions: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        call = self.calls[pending.call_index]
        call["response_frame"] = frame_index
        call["response"] = redact(message)
        call["status"] = (
            "error" if isinstance(message, Mapping) and "error" in message else "completed"
        )
        call["latency_ms"] = round((time.monotonic() - pending.started_monotonic) * 1000, 3)
        call["interventions"] = redact(list(interventions))
        self.pending.pop(pending.key, None)

    def finalize(self, exit_code: int | None, proxy_error: str | None = None) -> dict[str, Any]:
        for pending in list(self.pending.values()):
            self.calls[pending.call_index]["status"] = "unresolved"
        document: dict[str, Any] = {
            "schema_version": CASSETTE_SCHEMA,
            "created_at": self.started_at,
            "ended_at": datetime.now(UTC).isoformat(),
            "transport": "stdio",
            "upstream_argv": self.argv,
            "metadata": self.metadata,
            "frames": self.frames,
            "calls": self.calls,
            "upstream_exit_code": exit_code,
        }
        if proxy_error:
            document["proxy_error"] = redact(proxy_error)
        document["cassette_sha256"] = _cassette_digest(document)
        return document

    def write(
        self, path: str | Path, exit_code: int | None, proxy_error: str | None = None
    ) -> dict[str, Any]:
        document = self.finalize(exit_code=exit_code, proxy_error=proxy_error)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".groundflip-cassette-", dir=target.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as output:
                json.dump(document, output, indent=2, sort_keys=True, ensure_ascii=False)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return document


def verify_cassette(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != CASSETTE_SCHEMA:
        errors.append("unsupported cassette schema")
    expected = document.get("cassette_sha256")
    if not isinstance(expected, str) or not hmac_compare(expected, _cassette_digest(document)):
        errors.append("cassette SHA-256 mismatch")
    frames = document.get("frames")
    if not isinstance(frames, list):
        return errors + ["frames must be a list"]
    for index, frame in enumerate(frames):
        if not isinstance(frame, Mapping):
            errors.append(f"frame {index} is not an object")
            continue
        raw = frame.get("raw")
        if not isinstance(raw, str) or frame.get("raw_sha256") != _sha256_text(raw):
            errors.append(f"frame {index} raw hash mismatch")
        message = frame.get("message")
        expected_message = _sha256_text(canonical_json(message)) if message is not None else None
        if frame.get("message_sha256") != expected_message:
            errors.append(f"frame {index} message hash mismatch")
    return errors


def hmac_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def load_cassette(path: str | Path, *, verify: bool = True) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if verify:
        errors = verify_cassette(document)
        if errors:
            raise CassetteIntegrityError("; ".join(errors))
    return document


def _pointer_tokens(path: str) -> tuple[str | int, ...]:
    if not path.startswith("/"):
        raise CassetteInterventionError("JSON Pointer must start with '/'")
    tokens: list[str | int] = []
    for raw in path.split("/")[1:]:
        value = raw.replace("~1", "/").replace("~0", "~")
        tokens.append(int(value) if re.fullmatch(r"0|[1-9][0-9]*", value) else value)
    return tuple(tokens)


def _jsonpath_tokens(path: str) -> tuple[str | int, ...]:
    from .jsonpath import parse

    return parse(path)


def _path_tokens(path: str) -> tuple[str | int, ...]:
    tokens = _pointer_tokens(path) if path.startswith("/") else _jsonpath_tokens(path)
    if tokens and tokens[0] == "result":
        tokens = tokens[1:]
    return tokens


def _replace_path(document: Any, path: str, value: Any) -> Any:
    tokens = _path_tokens(path)
    if not tokens:
        raise CassetteInterventionError("Cannot replace the whole result")
    output = copy.deepcopy(document)
    current = output
    for token in tokens[:-1]:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise CassetteInterventionError(f"Path not found: {path}")
        elif not isinstance(current, dict) or token not in current:
            raise CassetteInterventionError(f"Path not found: {path}")
        current = current[token]
    leaf = tokens[-1]
    if isinstance(leaf, int):
        if not isinstance(current, list) or leaf >= len(current):
            raise CassetteInterventionError(f"Path not found: {path}")
    elif not isinstance(current, dict) or leaf not in current:
        raise CassetteInterventionError(f"Path not found: {path}")
    current[leaf] = copy.deepcopy(value)
    return output


def _subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(actual, Mapping) and all(
            key in actual and _subset(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_subset(a, b) for a, b in zip(expected, actual, strict=False))
        )
    return type(expected) is type(actual) and expected == actual


@dataclass(frozen=True)
class Intervention:
    rule_id: str
    tool_name: str
    path: str
    value: Any
    arguments: Any = None
    request_id: Any = None
    has_request_id: bool = False
    occurrence: int | None = None


class InterventionEngine:
    def __init__(self, rules: Iterable[Intervention] = ()) -> None:
        self.rules = tuple(rules)
        self.counts: dict[str, int] = {}

    @classmethod
    def from_file(cls, path: str | Path | None) -> InterventionEngine:
        if path is None:
            return cls()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = raw if isinstance(raw, list) else raw.get("interventions", [])
        if not isinstance(entries, list):
            raise CassetteInterventionError("interventions must be a list")
        rules: list[Intervention] = []
        for index, item in enumerate(entries):
            if not isinstance(item, Mapping):
                raise CassetteInterventionError(f"intervention {index} must be an object")
            match = item.get("match", {})
            match = match if isinstance(match, Mapping) else {}
            tool = item.get("tool_name", item.get("tool"))
            if not isinstance(tool, str) or not isinstance(item.get("path"), str):
                raise CassetteInterventionError(f"intervention {index} needs tool and path")
            has_request_id = "request_id" in item or "request_id" in match
            value_present = "value" in item or "replace" in item
            if not value_present:
                raise CassetteInterventionError(f"intervention {index} needs value")
            rules.append(
                Intervention(
                    rule_id=str(item.get("id", f"rule-{index}")),
                    tool_name=tool,
                    path=item["path"],
                    value=item.get("value", item.get("replace")),
                    arguments=item.get("arguments", match.get("arguments")),
                    request_id=item.get("request_id", match.get("request_id")),
                    has_request_id=has_request_id,
                    occurrence=item.get("occurrence"),
                )
            )
        return cls(rules)

    def apply_response(
        self,
        *,
        tool_name: str,
        arguments: Any,
        request_id: Any,
        response: Any,
    ) -> tuple[Any, list[dict[str, Any]]]:
        output = copy.deepcopy(response)
        events: list[dict[str, Any]] = []
        for rule in self.rules:
            if rule.tool_name != tool_name:
                continue
            if rule.arguments is not None and not _subset(rule.arguments, arguments):
                continue
            if rule.has_request_id and canonical_request_id(
                rule.request_id
            ) != canonical_request_id(request_id):
                continue
            self.counts[rule.rule_id] = self.counts.get(rule.rule_id, 0) + 1
            occurrence = self.counts[rule.rule_id]
            if rule.occurrence is not None and rule.occurrence != occurrence:
                continue
            event = {
                "rule_id": rule.rule_id,
                "tool_name": tool_name,
                "path": rule.path,
                "occurrence": occurrence,
                "status": "path_not_found",
            }
            if not isinstance(output, Mapping) or "result" not in output:
                event["status"] = "no_result"
                events.append(event)
                continue
            before = redact(output["result"])
            try:
                changed_result = _replace_path(output["result"], rule.path, rule.value)
            except CassetteInterventionError:
                events.append(event)
                continue
            output = dict(output)
            output["result"] = changed_result
            event.update(
                {
                    "status": "replaced",
                    "before_sha256": _sha256_text(canonical_json(before)),
                    "after_sha256": _sha256_text(canonical_json(redact(changed_result))),
                }
            )
            events.append(event)
        return output, events
