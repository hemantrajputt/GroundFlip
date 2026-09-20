# Contract DSL reference

## Required fields

```yaml
version: 1
name: stable-human-name
scenario: relative/or/absolute.json
target: {kind: claim|action, path: $.output.path}
evidence: {tool: namespace.tool, path: $.result.path}
mutation: {op: replace, value: 17}
expect: {relation: tracks_value}
```

Paths support `$`, dotted keys, quoted bracket keys, and non-negative list
indices. Filters, recursive descent, wildcards, negative indices, and script
expressions are rejected.

## Evidence selector

| Field | Meaning |
|---|---|
| `tool` | Exact MCP tool name |
| `path` | Path inside the tool's `structuredContent` |
| `call_id` | Optional exact captured call identifier |
| `source_type` | `mcp`, `user`, `prior`, `policy`, `untrusted`, etc. |
| `sole_support` | Required for a strong abstention expectation |
| `equivalence_class` | Group duplicate/correlated evidence for one intervention |

## Mutations

- `replace`: replace an existing scalar/object at the path.
- `delete`: remove an optional property/list item.
- `null`: set an existing path to null.
- `add`: add a numeric delta.
- `swap`: exchange the value with `other_path`.

Every non-delete mutation must actually change the value. When an output schema
is present, the whole mutated object must remain valid.

## Relations

| Relation | Oracle |
|---|---|
| `changes_to` | intervention target equals declared `value` (or mutated evidence) |
| `tracks_value` | intervention target equals the mutated evidence value |
| `invariant` | paired control and intervention target are equal |
| `monotonic_increase` | numeric intervention target is greater than control |
| `monotonic_decrease` | numeric intervention target is less than control |
| `abstains` | target is absent/null or in `abstention_values` |
| `rejects_source` | unauthorized-source mutation leaves target invariant |

## Repetition and verdicts

`runs` is 1–100; `alpha` controls Wilson intervals; `max_control_churn` is the
allowed identical-control noise floor; `min_pass_rate` is the relational success
threshold. Excess churn forces `INCONCLUSIVE`. Mixed results whose interval still
crosses the threshold are also inconclusive rather than optimistic passes.

