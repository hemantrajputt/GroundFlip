# Protocol support matrix

GroundFlip's relay is intentionally raw JSON-RPC. “Supported” means tested
capture/pass-through behavior, not full semantic validation of every MCP method.

| Surface | v0.1 status | Evidence / limitation |
|---|---|---|
| stdio | Supported | Newline-delimited JSON-RPC; protocol stdout remains clean |
| MCP `2026-07-28` | Interop tested | Official Python SDK 2.0.0 high-level `Client`; `server/discover` observed through proxy |
| legacy initialize flow | Interop tested | Official SDK 1.26.0 and 2.0.0 `ClientSession` |
| `tools/list` | Pass-through tested | Official SDK catalogs traverse the relay |
| `tools/call` | Capture + correlate | Type-tagged request IDs; result/error/unresolved status |
| `structuredContent` | Intervention tested | Official SDK client observes replacement; fixture counter proves one upstream call |
| large frames | Bounded support | 100,000-byte result passes; configurable 16 MiB default; larger frames fail closed |
| notifications | Pass-through | No request/response correlation |
| text content | Captured | Text-to-JSON intervention is not automatic |
| resources/prompts | Pass-through only | Not v0.1 intervention targets |
| Streamable HTTP | Not supported | Roadmap item |
| SSE | Not supported | Roadmap item |
| cancellation/progress | Pass-through | Dedicated lifecycle coverage remains incomplete |
| write/destructive tools | Original call only | Counterfactual synthesis never calls upstream again |

The relay preserves unknown message members and does not hard-code a protocol
revision. Method-aware behavior is limited to `tools/call`. Duplicate in-flight
request IDs are protocol-invalid and not a supported concurrency pattern; an
explicit rejection guard is still pending. Non-UTF-8 frames pass through, but
the cassette's human-readable raw field is loss-aware rather than a byte-perfect
forensic encoding.

Interop tests run through a real official client → GroundFlip subprocess → real
official server, on Windows locally and on Windows/Ubuntu in CI configuration.
That is meaningful compatibility evidence, not a claim of universal MCP support.
