# Build journal

This is an evidence log, not a polished retrospective.

## 2026-08-07 — product reset

The first direction was rejected as generic. A current landscape scan showed
that trace/replay, MCP snapshot diffing, provenance verification, generic
metamorphic tests, and step-level causal replay were already occupied. The
working name `TraceForge` also collided with an existing package. Decision:
clean-room **GroundFlip**, narrowed to claim/action ↔ exact evidence-path
behavioral contracts.

The product spec defines non-claims and kill criteria before implementation:
≥95% intervention validity, ≥0.85 planted-edge F1, ≥0.90 precision at ≥0.80
defect recall, ≥20-point recall improvement over static checking, ≤15% control
churn, and a useful ≤3x paired-contract mode.

## Implementation choices

- Raw stdio proxy so unknown JSON-RPC fields survive protocol evolution.
- Synthesis-only branching so write-capable tools are never repeated.
- Restricted JSONPath/Pointer parser; deterministic typed oracles first.
- Randomized paired branches, Wilson intervals, and identical-control churn.
- Environment-only optional OpenAI Responses adapter with `store=False`.
- Redacted canonical storage; signed authentication policy; optional HMAC.

## Failures that changed the design

- A broad recorder/replay product failed the novelty scan; evidence-dependence
  contracts became the product unit.
- The first benchmark called prefixed strings “held-out schemas” without
  executing payload mutation. It was rebuilt around real nested JSON payloads,
  strict inferred schemas, production intervention code, and four disjoint
  templates. Wording now says shape coverage—not model generalization.
- `stale_cache` was incorrectly counted as tracking because stale and flipped
  values both mapped to `HIGH`. Tracking now requires the expected control →
  intervention transition.
- Intervention validity and call ratios were constants. The artifact now counts
  1,296 actual schema-validation attempts and labels execution counts as
  simulated synthesis observations, not API calls.
- Initial dependency F1 compared to intended paths even for cross-wired fixtures;
  it now measures recovery of planted actual edges, while correctness stays a
  separate contract metric.
- The asyncio default reader failed an official SDK tool result above 64 KiB.
  A configurable 16 MiB limit plus explicit rejection and lifecycle handling
  fixed the 100,000-byte round trip.
- The first HMAC certificate could be downgraded by replacing its authentication
  block with a recomputed checksum. The required method/key ID is now in the
  authenticated payload, and verifiers can require HMAC.
- The first package build rejected a PEP 639 license classifier combination;
  metadata was corrected, then wheel/sdist and a clean-venv install passed.
- Windows sandbox ACL setup repeatedly failed; edits used verified same-directory
  backups plus clean recreation, and every temporary backup was removed.
- The in-app browser preview was unavailable. Responsive/print/CSP/escaping
  behavior has automated tests, but screenshot-based report QA remains pending.
- No `OPENAI_API_KEY` was present. No live-model metric is substituted or claimed.

## Verified checkpoints

- Main environment: **55 tests passed**, **87% coverage**, Ruff clean.
- Official MCP SDK 1.26.0: legacy client → proxy → FastMCP server passes,
  including a 100,000-byte result and one-call intervention.
- Isolated official MCP SDK 2.0.0: both legacy `ClientSession` tests pass; modern
  high-level client negotiates protocol `2026-07-28` via `server/discover`.
- Deterministic full benchmark: 72 cases × 6 behaviors = 432 evaluations;
  static 72/360 defects (20% recall), GroundFlip 360/360 with 0/72 false
  positives; planted-edge F1 1.00; mutations 1,296/1,296 schema-valid.
- Benchmark SHA-256:
  `92c17a806672d72cd81711da36e262d1d2e894179882e9a8c2680db510825e4e`.
- Editable install, wheel, sdist, metadata check, and clean-wheel `pip check`
  passed. The project is locally release-ready but not published.

## Remaining evidence work

- Run and publish separate live-model repetitions once an environment key exists.
- Complete screenshot/print visual QA in an available browser surface.
- Add external/fuzz/independent security testing and duplicate-ID guards.
- Publish only after the user chooses a repository and package namespace.
