# GroundFlip v0.1 Product Specification

Status: implementation contract, 2026-08-07

## Thesis

GroundFlip is an open-source causal contract tester for MCP-grounded agents.
It records the evidence a model consumed, changes one controlled evidence field,
re-runs the same synthesis boundary, and tests whether downstream claims and
action arguments change—or remain invariant—exactly as declared.

The product does **not** claim to prove real-world truth, expose hidden model
reasoning, or invent counterfactual replay. It estimates black-box behavioral
dependence under controlled interventions.

## User and job

The primary user is an engineer shipping a tool-using agent. Their question is:

> The tool call succeeded and the answer looks plausible. Did the answer
> actually use the right tool field, or was the call decorative, stale, or
> cross-wired?

GroundFlip turns one observed run into executable evidence contracts suitable
for local debugging and CI.

## Novelty boundary

Existing categories already cover trace collection, MCP server snapshots,
generic mutation testing, source-support scoring, and step-level causal replay.
GroundFlip's unit of testing is narrower: a typed relationship between one MCP
evidence path and one downstream claim or action argument.

The v0.1 novelty bar requires all of the following:

1. Protocol-level MCP stdio capture, independent of an agent framework.
2. Linkage from original MCP result bytes to the exact normalized evidence
   object supplied at the synthesis boundary.
3. JSONPath-like, schema-valid scalar interventions.
4. Relational contracts for follow, invariance, abstention, monotonicity, and
   source authority.
5. Interleaved paired controls and interventions across repeated stochastic
   runs, with PASS/FAIL/INCONCLUSIVE verdicts and confidence intervals.
6. Claim- and action-argument-level evidence influence records.
7. A portable, content-addressed test certificate and human-readable report.
8. A mechanically generated held-out benchmark with planted wiring defects.

## Supported v0.1 surface

- Read-only MCP tools over stdio.
- `structuredContent` or JSON-parseable text results.
- Numeric, boolean, categorical, and ISO date claims.
- Frozen synthesis replay; side-effectful tools are never re-executed.
- OpenAI Responses provider plus a provider protocol and offline scripted
  provider for CI.
- Local JSONL/content-addressed storage; no hosted service.
- CLI, JSON/Markdown certificate, and self-contained HTML report.

## Contract DSL

```yaml
version: 1
name: procurement-price-threshold
scenario: examples/procurement/scenario.json
target:
  kind: claim
  path: $.decision
evidence:
  tool: procurement.get_quote
  path: $.price
mutation:
  op: replace
  value: 125000
expect:
  relation: changes_to
  value: ESCALATE
controls:
  - target: $.vendor
    relation: invariant
runs: 5
alpha: 0.05
max_control_churn: 0.15
```

Relations:

- `changes_to`: target equals the declared value after intervention.
- `tracks_value`: target follows the mutated evidence value.
- `invariant`: target is stable under a placebo intervention.
- `monotonic_increase` / `monotonic_decrease`: numeric action/claim moves in
  the declared direction.
- `abstains`: target is removed, null, or matches a configured abstention set
  when sole support is removed.
- `rejects_source`: unauthorized-source content does not control the target.

## Execution model

1. Record a baseline MCP exchange and synthesis request.
2. Canonicalize and hash schemas, calls, results, prompts, and model settings.
3. Extract typed output observations with deterministic parsers first.
4. Resolve the contract's exact evidence path and validate the mutation.
5. Produce a control branch and an intervention branch from the same snapshot.
6. Randomize/interleave branch order and run each branch `N` times.
7. Compare target behavior against exact relational oracles; semantic model
   judging is never the primary oracle for supported types.
8. Estimate effect, control churn, Wilson confidence intervals, and verdict.
9. Emit certificate, influence matrix, raw run references, and CI exit code.

## Duplicate evidence and source types

Evidence records have source types (`mcp`, `user`, `prior`, `policy`) and may
belong to an equivalence class. GroundFlip only expects abstention when the
mutated field or group is declared sole support. Equivalent duplicate evidence
must be ablated as a group to avoid false independence findings.

## Safety model

- Only captured results are mutated; tools are not re-executed during a branch.
- Tool annotations are treated as untrusted hints. The scenario must explicitly
  allow recording and replay.
- Secrets are redacted before persistence and tested against common credential
  formats.
- Commands in scenario files require an explicit CLI opt-in.
- Certificates contain checksums of what was tested. Integrity requires an
  independently pinned digest or HMAC verification key; neither is a truth claim.

## CLI contract

```text
groundflip demo [--provider scripted|openai]
groundflip record --command ... --out run.json
groundflip test contract.yml [--provider ...] [--allow-command]
groundflip certify result.json --out certificate.json
groundflip report certificate.json --out report.html
groundflip benchmark [--tier smoke|full] [--provider ...]
groundflip gate certificate.json
groundflip proxy --cassette cassette.json -- command [args...]
```

## Benchmark: EvidenceWireBench

The benchmark generates fresh, high-entropy evidence so a model cannot know the
answer parametrically. Domains are commerce metrics, incident telemetry, and
inventory/procurement. Held-out cases use unseen object shapes.

Planted agent behaviors:

- grounded: reads the intended field;
- answer-before-tool: returns a cached baseline;
- stale-cache: uses an earlier result;
- cross-wired: reads a correlated but unauthorized field;
- distractor-sensitive: copies irrelevant content;
- unsupported-persistence: retains a claim after sole support is removed.

Primary metrics:

- Counterfactual Tracking Rate;
- Unsupported Persistence Rate;
- Placebo Stability;
- Control Churn;
- evidence-path mapping precision/recall/F1;
- defect detection precision/recall;
- schema/intervention validity;
- calls, tokens, latency, and cost per audited target.

The static baseline checks only whether the unmodified final output is correct
and supported. The benchmark must demonstrate incremental hidden-defect recall,
not merely a polished report.

## Precommitted kill criteria

The portfolio claim is withdrawn if any of these hold on the held-out tier:

- control churn exceeds 15% after five repeats;
- intervention validity is below 95% on supported types;
- evidence-path mapping F1 is below 0.85;
- defect detection is below 0.90 precision at 0.80 recall;
- incremental recall over the static baseline is below 20 percentage points;
- median audit cost exceeds 3x original synthesis cost without a useful
  one-sample mode;
- the implementation only works with GroundFlip's own fixture server.

## Out of scope for v0.1

- Replaying write/destructive tools.
- Claims about formal causal identification or internal reasoning.
- Automatic agent repair or prompt optimization.
- Generic observability, hosted dashboards, or framework-specific tracing.
- Free-text factuality as a primary benchmark oracle.
- Prompt-injection testing (a future contract plugin, not a v0.1 claim).

