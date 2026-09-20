import asyncio
import io
import json
import sys
from pathlib import Path

import pytest

from groundflip.cassette import load_cassette
from groundflip.mcp_proxy import ProxyError, run_proxy

FIXTURE = Path(__file__).parent / "fixtures" / "echo_mcp_server.py"


def test_proxy_rejects_over_limit_client_frame_and_records_error(tmp_path):
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "echo", "arguments": {"blob": "x" * 2_000}},
    }
    source = io.BytesIO((json.dumps(request) + "\n").encode())
    cassette = tmp_path / "over-limit.json"
    with pytest.raises(ProxyError, match="client frame exceeds"):
        asyncio.run(
            run_proxy(
                [sys.executable, str(FIXTURE)],
                cassette,
                stdin=source,
                stdout=io.BytesIO(),
                stderr=io.BytesIO(),
                max_frame_bytes=1_024,
            )
        )
    document = load_cassette(cassette)
    assert "client frame exceeds" in document["proxy_error"]
    assert document["metadata"]["max_frame_bytes"] == 1_024
