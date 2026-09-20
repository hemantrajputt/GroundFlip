# Architecture

GroundFlip separates evidence capture from model synthesis so an experiment can
hold the model-visible state fixed and change only a declared evidence field.

```text
                     capture plane
agent / MCP client ─────────────────► GroundFlip stdio proxy ─► MCP server
                                           │
                                           ▼
                                  redacted cassette + hashes
                                           │
                     experiment plane      ▼
contract ─► schema validator ─► control snapshot + intervention snapshot
                                           │
                         randomized paired │ synthesis runs
                                           ▼
                               structured observations
                                           │
                   exact relation oracle + noise floor + Wilson interval
                                           │
                         certificate ─► HTML report ─► CI gate
```

## Boundaries

### Wire capture

`mcp_proxy.py` is a raw newline-delimited JSON-RPC relay. It does not reconstruct
messages with an MCP SDK unless a selected result is actually mutated. This
preserves unknown extension fields and keeps the relay protocol-version tolerant.
`cassette.py` correlates `tools/call` requests by type-tagged JSON-RPC ID, redacts
before persistence, hashes frames, and writes atomically.

### Frozen synthesis snapshot

A `Scenario` contains the prompt, system instructions, exact structured tool
results, output schemas, source types, and metadata visible at the synthesis
boundary. Branching here is intentional: GroundFlip never re-executes a captured
write. A result intervention is therefore one upstream call plus two or more
model syntheses, not a duplicate side effect.

### Intervention engine

The core supports replace, delete, null, numeric-add, and swap over a restricted,
non-evaluating JSONPath subset. Mutated MCP `structuredContent` is checked against
the tool's JSON Schema 2020-12 output schema before any model call. Invalid and
no-op mutations fail closed.

### Relational oracle

`ContractRunner` randomizes control/intervention order for each pair. Supported
typed relations are exact follow, invariance, monotonic movement, abstention,
and source rejection. LLM judging is not the primary oracle for v0.1 types.
Identical-control churn is a measured noise floor; excessive churn yields
`INCONCLUSIVE` rather than a causal-sounding pass/fail.

### Influence mapper

`influence.py` probes candidate tool-result fields and builds a claim/action to
evidence-path matrix from observed paired effects. A field is marked influential
only when its effect rate clears both a configured threshold and the control
noise margin. This discovers wrong-source dependencies separately from checking
whether a declared dependency is correct.

### Providers

The provider protocol is one method: synthesize a structured observation from a
scenario, branch name, and experiment seed. The scripted provider is transparent
CI infrastructure. The live adapter uses the OpenAI Responses API, strict JSON
Schema output, `store=False`, and environment-only credentials.

### Integrity artifacts

The content-addressed store and cassettes hash redacted canonical JSON. A
certificate is an in-toto-shaped statement with a SHA-256 payload digest and
optional HMAC. It deliberately is not advertised as a DSSE signature or proof of
source truth.

## Data models

- `Scenario`: frozen prompt, evidence, schema, metadata.
- `Contract`: evidence selector, mutation, output target, relational assertion.
- `BranchRun`: paired provider outputs and exact oracle outcomes.
- `ContractResult`: effect, churn, intervals, hashes, verdict.
- `InfluenceMap`: tested claim/action × evidence-path edges.
- `Cassette`: raw/redacted frames, correlated calls, applied interventions.
- `Certificate`: portable result statement and integrity metadata.

## Dependency policy

The runtime core uses only PyYAML and `jsonschema`. OpenAI is an optional extra.
The MCP proxy deliberately uses the Python standard library so wire capture is
not coupled to an SDK model that may discard future extension fields.

