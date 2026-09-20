import asyncio
import io
import json
import sys
from pathlib import Path

from groundflip.cassette import load_cassette
from groundflip.mcp_proxy import run_proxy

FIXTURE = Path(__file__).parent / "fixtures" / "echo_mcp_server.py"


def _line(message):
    return (json.dumps(message, separators=(",", ":")) + "\n").encode()


def test_stdio_proxy_records_relays_and_intervenes_once(tmp_path):
    request = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "echo", "arguments": {"price": 42}},
    }
    source = io.BytesIO(_line(request))
    output = io.BytesIO()
    errors = io.BytesIO()
    intervention = tmp_path / "intervention.json"
    intervention.write_text(
        json.dumps(
            {
                "interventions": [
                    {
                        "tool": "echo",
                        "path": "$.structuredContent.echo.price",
                        "value": 17,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cassette = tmp_path / "run.json"
    result = asyncio.run(
        run_proxy(
            [sys.executable, str(FIXTURE)],
            cassette,
            intervention,
            stdin=source,
            stdout=output,
            stderr=errors,
        )
    )
    response = json.loads(output.getvalue())
    assert response["result"]["structuredContent"]["echo"]["price"] == 17
    assert response["result"]["structuredContent"]["counter"] == 1
    assert response["x-fixture-extension"]["preserved"] is True
    assert b"fixture-call" in errors.getvalue()
    document = load_cassette(cassette)
    assert result.tool_calls == 1
    assert document["calls"][0]["interventions"][0]["status"] == "replaced"
    assert document["calls"][0]["status"] == "completed"


def test_proxy_stdout_contains_no_groundflip_diagnostics(tmp_path):
    source = io.BytesIO(_line({"jsonrpc": "2.0", "id": "1", "method": "initialize", "params": {}}))
    output = io.BytesIO()
    asyncio.run(
        run_proxy(
            [sys.executable, str(FIXTURE)],
            tmp_path / "run.json",
            stdin=source,
            stdout=output,
            stderr=io.BytesIO(),
        )
    )
    lines = output.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == "1"
