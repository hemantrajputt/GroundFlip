"""Compatibility fixture implemented only with the official MCP Python SDK."""

try:
    from mcp.server import MCPServer
except ImportError:  # MCP SDK v1 maintenance line
    from mcp.server.fastmcp import FastMCP as MCPServer

mcp = MCPServer("groundflip-official-sdk-interop")
_calls = 0


@mcp.tool()
def echo(payload: str, blob_size: int = 0) -> dict[str, object]:
    """Return structured data and an optional payload larger than 64 KiB."""
    global _calls
    _calls += 1
    return {
        "echo": f"ORIGINAL:{payload}",
        "counter": _calls,
        "blob": "x" * blob_size,
    }


if __name__ == "__main__":
    mcp.run()
