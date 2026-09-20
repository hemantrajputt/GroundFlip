import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

from groundflip.cassette import load_cassette  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "official_mcp_server.py"


def _structured(result):
    return getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)


async def _call_through_proxy(cassette, *, intervention=None, blob_size=0):
    arguments = [
        "-m",
        "groundflip.mcp_proxy",
        "--cassette",
        str(cassette),
    ]
    if intervention is not None:
        arguments.extend(["--interventions", str(intervention)])
    arguments.extend(["--", sys.executable, str(FIXTURE)])
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[1] / "src")
    environment["PYTHONPATH"] = source_root + os.pathsep + environment.get("PYTHONPATH", "")
    params = StdioServerParameters(command=sys.executable, args=arguments, env=environment)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await asyncio.wait_for(session.initialize(), timeout=20)
        tools = await asyncio.wait_for(session.list_tools(), timeout=20)
        assert "echo" in {tool.name for tool in tools.tools}
        return await asyncio.wait_for(
            session.call_tool("echo", {"payload": "wire-test", "blob_size": blob_size}),
            timeout=20,
        )


@pytest.mark.integration
def test_official_sdk_client_proxy_server_and_large_frame(tmp_path):
    cassette = tmp_path / "sdk.json"
    result = asyncio.run(_call_through_proxy(cassette, blob_size=100_000))
    structured = _structured(result)
    assert structured["echo"] == "ORIGINAL:wire-test"
    assert structured["counter"] == 1
    assert len(structured["blob"]) == 100_000
    document = load_cassette(cassette)
    assert len(document["calls"]) == 1
    assert document["calls"][0]["tool_name"] == "echo"


@pytest.mark.integration
def test_official_sdk_client_observes_one_call_intervention(tmp_path):
    intervention = tmp_path / "intervention.json"
    intervention.write_text(
        json.dumps(
            {
                "interventions": [
                    {
                        "id": "sdk-echo",
                        "tool": "echo",
                        "path": "$.structuredContent.echo",
                        "value": "INTERVENED",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    cassette = tmp_path / "sdk-intervened.json"
    result = asyncio.run(_call_through_proxy(cassette, intervention=intervention))
    structured = _structured(result)
    assert structured["echo"] == "INTERVENED"
    assert structured["counter"] == 1
    document = load_cassette(cassette)
    assert len(document["calls"]) == 1
    assert document["calls"][0]["interventions"][0]["status"] == "replaced"
