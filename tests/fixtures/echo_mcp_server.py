"""Tiny JSON-RPC stdio fixture; intentionally uses no MCP SDK."""

from __future__ import annotations

import json
import sys

counter = 0
for raw in sys.stdin.buffer:
    try:
        message = json.loads(raw)
    except json.JSONDecodeError:
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        continue
    if message.get("method") == "tools/call":
        counter += 1
        params = message.get("params", {})
        arguments = params.get("arguments", {})
        result = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "content": [{"type": "text", "text": json.dumps(arguments)}],
                "structuredContent": {"echo": arguments, "counter": counter},
                "isError": False,
            },
            "x-fixture-extension": {"preserved": True},
        }
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        print("fixture-call", file=sys.stderr, flush=True)
    elif "id" in message:
        result = {"jsonrpc": "2.0", "id": message["id"], "result": {"ok": True}}
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        sys.stdout.flush()
