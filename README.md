# GroundFlip

**Behavioral evidence-dependence testing for MCP-grounded agents.**

An agent can call the right tool, quote a plausible number, and still ignore the
result. GroundFlip tests the missing link: whether a specific downstream claim
or action actually follows the MCP evidence field it should use—and stays stable
when irrelevant evidence changes.

```text
recorded MCP result ── one schema-valid field flip ──► paired synthesis runs
          │                                                │
          └──────────────── evidence contract ◄─────────────┘
```

GroundFlip is not another trace viewer, cassette recorder, or LLM judge. It turns
traces into executable relationships:

- if `get_quote.price` crosses policy, `decision` must become `ESCALATE`;
- if an irrelevant marketing score changes, `decision` must remain invariant;
- if sole support disappears, the claim must abstain;
- if evidence rises, an action argument must move monotonically.

GroundFlip estimates black-box behavioral dependence under controlled
interventions. It does not prove source truth, internal reasoning, or formal
causality.

## Five-minute demo

GroundFlip requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
groundflip demo
```

The demo runs four contracts against a grounded procurement fixture and four
planted defects. It writes paired results, certificates, and self-contained HTML
reports to `.groundflip/demo/`.

```bash
groundflip test examples/procurement/contract.yml
groundflip benchmark --tier smoke
```

## A contract, not a golden answer

```yaml
version: 1
name: procurement-price-threshold
scenario: scenario.json
target: {kind: action, path: $.decision}
evidence: {tool: procurement.get_quote, path: $.price}
mutation: {op: replace, value: 125000}
expect: {relation: changes_to, value: ESCALATE}
controls:
  - {target: $.vendor, relation: invariant}
runs: 5
max_control_churn: 0.15
```

Control and intervention branches start from the same recorded snapshot.
GroundFlip randomizes branch order, repeats the pair, reports Wilson intervals,
and returns `PASS`, `FAIL`, or `INCONCLUSIVE`. Identical-control churn prevents
provider noise from masquerading as an intervention effect.

## Live model adapter

The scripted adapter is reproducible test infrastructure, not model evidence.
For a live model, install the optional adapter and set the key only in the
environment:

```bash
pip install -e ".[openai]"
# PowerShell
$env:OPENAI_API_KEY = "..."
groundflip demo --provider openai --runs 5
```

The adapter uses the OpenAI Responses API with strict structured output and
`store=False`. The default model is `gpt-5.6-terra`; override it with
`GROUNDFLIP_OPENAI_MODEL` or `--model`. Keys are never loaded from contracts or
written to artifacts. No live-model result is claimed in this repository yet.

## MCP wire capture

Use the stdio proxy as the command in an MCP client configuration. It preserves
unknown JSON-RPC members, correlates `tools/call` results, and records a redacted
cassette without writing diagnostics to protocol stdout.

```bash
groundflip proxy --allow-command --cassette run.json -- python my_server.py
```

Frames are bounded to 16 MiB by default; use `--max-frame-bytes` to choose a
tighter limit. A 100,000-byte tool result is covered by regression tests. The
relay has been exercised end-to-end with the official MCP Python SDK 1.26.0 and
2.0.0, including a v2 `server/discover` negotiation of protocol `2026-07-28`.

Intervention files can replace selected result paths in flight. The upstream
tool is called once; paired synthesis consumes recorded results and never repeats
the tool side effect.

## Certificates and reports

A certificate contains the contract, evidence path, mutation, provider/model
metadata, repeated outcomes, branch-output hashes, intervals, control churn, and
verdict. All hashes cover redacted canonical artifacts.

- SHA-256 is a checksum/content address. It detects change only when the expected
  digest is pinned independently.
- Optional HMAC-SHA256 authenticates the artifact to holders of the shared key.
  The required method is signed, and verification can require HMAC to prevent a
  downgrade to a recomputed checksum.

Neither mode authenticates evidence truth.

```bash
groundflip certify run.result.json --out run.certificate.json
groundflip report run.certificate.json --out run.html
groundflip gate run.certificate.json
```

Reports are zero-CDN HTML with CSP, escaping, responsive table overflow, print
styles, run rows, warnings, and explicit integrity labeling.

## EvidenceWireBench

EvidenceWireBench generates nested MCP-like payloads, strict Draft 2020-12
schemas, seeded facts, targeted flips, null ablations, placebos, and six planted
agent wiring behaviors. No judge model writes or grades the oracle.

The checked-in deterministic full run contains 72 cases and 432 evaluations:

- static final-answer check: 72/360 planted defects found (20% recall);
- GroundFlip contracts: 360/360 found with 0/72 false positives (100% recall);
- planted dependency-edge recovery: 1.00 F1;
- schema-valid mutations: 1,296/1,296;
- 24 cases use four nested templates disjoint from the held-in fixture template.

These are co-designed harness tests, not independent validation or hosted-model
performance. See the [benchmark card](benchmarks/BENCHMARK_CARD.md),
[raw result](benchmarks/results/offline-full.json), and
[precommitted kill criteria](docs/PRODUCT_SPEC.md#precommitted-kill-criteria).

## Scope

GroundFlip v0.1 supports:

- read-only MCP tools over stdio;
- JSON `structuredContent` or JSON-parseable text;
- numeric, boolean, categorical, and ISO-date observations;
- replace, delete, null, numeric-add, and swap interventions;
- follow, invariance, monotonicity, abstention, and source-authority contracts;
- provider-neutral synthesis plus an OpenAI Responses adapter;
- local cassettes, JSON/Markdown certificates, and self-contained HTML reports.

It does not execute contract code, replay write tools, promise deterministic
hosted-model output, or use an LLM judge as the primary oracle.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
python -m build
```

Official MCP v2 interop is an optional release gate:

```bash
pip install -e ".[dev,interop]"
pytest tests/test_mcp_sdk_interop.py tests/test_mcp_v2_modern_interop.py
```

Security reports belong in the private channel described in
[SECURITY.md](SECURITY.md). Contributions are welcome under the
[Apache-2.0 license](LICENSE).
