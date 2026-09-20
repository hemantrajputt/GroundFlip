import asyncio
import os
import sys
from pathlib import Path

import mcp
import pytest

Client = getattr(mcp, "Client", None)
if Client is None:
    pytest.skip("MCP SDK v2 high-level Client is not installed", allow_module_level=True)

from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

from groundflip.cassette import load_cassette  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "official_mcp_server.py"


@pytest.mark.integration
def test_mcp_v2_modern_protocol_negotiates_through_raw_proxy(tmp_path):
    cassette = tmp_path / "mcp-v2-modern.json"
    arguments = [
        "-m",
        "groundflip.mcp_proxy",
        "--cassette",
        str(cassette),
        "--",
        sys.executable,
        str(FIXTURE),
    ]
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = source_root + os.pathsep + environment.get("PYTHONPATH", "")
    params = StdioServerParameters(command=sys.executable, args=arguments, env=environment)

    async def exercise():
        async with Client(stdio_client(params)) as client:
            assert str(client.protocol_version) == "2026-07-28"
            tools = await asyncio.wait_for(client.list_tools(), timeout=20)
            assert "echo" in {tool.name for tool in tools.tools}
            return await asyncio.wait_for(
                client.call_tool("echo", {"payload": "modern", "blob_size": 0}), timeout=20
            )

    result = asyncio.run(exercise())
    assert result.structured_content["echo"] == "ORIGINAL:modern"
    document = load_cassette(cassette)
    assert len(document["calls"]) == 1
    assert any(
        frame.get("message", {}).get("method") == "server/discover"
        for frame in document["frames"]
        if isinstance(frame.get("message"), dict)
    )
