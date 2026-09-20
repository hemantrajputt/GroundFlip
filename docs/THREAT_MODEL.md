# Threat model

GroundFlip handles prompts, tool results, API metadata, and executable MCP server
commands. Treat every captured artifact and project file as untrusted.

## Assets and boundaries

Assets include provider credentials, private tool data, cassette/certificate
integrity, intervention correctness, absence of duplicate side effects, and the
developer/CI environment. Trust boundaries are client → proxy, proxy → upstream
server, captured evidence → synthesis request, contract → runner, and result →
certificate/report/gate.

## Threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Credential leakage | Recursive key/pattern redaction before hashing/persistence; regression tests | Encoded or novel secret formats may evade patterns |
| Tool-result prompt injection | Evidence is labeled untrusted and separated from instructions | Model behavior is not a security boundary; v0.1 does not claim injection defense |
| Duplicate write during replay | Branches use recorded results; upstream tool counter is one in integration tests | The original authorized live call can itself have effects |
| Malicious command | Contracts execute no code; proxy requires explicit `--allow-command` | An authorized command retains user OS permissions |
| Path-expression execution | Restricted parser; no `eval`, filters, wildcard, or recursion | Deep payloads can still consume resources |
| Impossible counterfactual called truth | Schema validation plus sensitivity-probe warning | Schemas cannot express every domain invariant |
| Noise mislabeled as effect | Randomized paired runs, Wilson intervals, identical-control churn gate | Provider drift remains possible |
| Duplicate evidence hides reliance | Equivalence classes and grouped intervention | Unknown support outside snapshot remains possible |
| Artifact rewrite | Per-frame/result hashes; signed required method; optional HMAC; constant-time compare | SHA-256 alone is not authentication; HMAC is shared-secret, not public-key attestation |
| HMAC downgrade | Verification key or `require_hmac=True` rejects checksum-only artifact | A verifier that requests checksum-only semantics receives no authentication |
| Report injection | Escaping, CSP, no JS/CDN/raw prompt, hostile-string tests | Opening arbitrary third-party HTML remains unsafe |
| Oversized frame/result | Configurable 16 MiB bound, >64 KiB and over-limit regression tests | Parent stdin reads a full line before length rejection |
| Subprocess hang/orphan | Concurrent stdout/stderr drains, daemon stdin pump, bounded terminate/kill | OS-level process-tree containment is not implemented |
| Local path substitution | Atomic same-directory cassette/store replacement | Hostile local filesystem owner remains out of scope |

## Side-effect policy

MCP tool annotations are untrusted hints, not authorization. GroundFlip records a
live call only after the surrounding client/user has authorized it. Branches
modify the captured result and replay synthesis; they do not repeat the tool.

## Certificate semantics

The certificate records redacted canonical artifacts, model/run metadata,
branch-output hashes, relational outcomes, and a verdict. SHA-256 is useful only
with an independently pinned digest. HMAC authenticates to shared-key holders and
prevents a downgrade when verification requires it. Neither says the source was
truthful or the model will behave identically tomorrow.

## Before production use

- add total-cassette/result-size quotas and per-run deadlines;
- reject duplicate in-flight IDs and bind occurrence matching at request arrival;
- persist invalid/non-UTF-8 frames as base64 for forensic byte fidelity;
- add external fuzzing of JSON-RPC relay, redaction, and path parser;
- commission an independent security review;
- add OS sandbox/shadow-state adapters for workflows that record writes;
- use managed asymmetric signing/DSSE for high-impact release gates.
