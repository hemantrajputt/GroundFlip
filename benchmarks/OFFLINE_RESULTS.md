# Offline benchmark results

Run: EvidenceWireBench full tier, seed `20260807`, 2026-08-07.

| Measure | Static final-answer check | GroundFlip contracts |
|---|---:|---:|
| Evaluations | 432 | 432 |
| Planted defects | 360 | 360 |
| True positives | 72 | 360 |
| False positives | 0 | 0 |
| Precision | 100% | 100% |
| Recall | 20% | 100% |
| F1 | 33.3% | 100% |
| Recall on 144 held-out-template evaluations | 20% | 100% |

Measured harness facts:

- hidden-defect recall improvement: **+80 percentage points**;
- planted dependency-edge recovery F1: **100%**;
- schema-valid production mutations: **1,296 / 1,296**;
- one paired contract: **2 simulated synthesis observations** versus 1 static
  observation;
- complete flip + ablation + placebo suite: **4 simulated observations**.

Artifact: [`results/offline-full.json`](results/offline-full.json)

SHA-256:

```text
92c17a806672d72cd81711da36e262d1d2e894179882e9a8c2680db510825e4e
```

## Interpretation

These numbers validate GroundFlip's deterministic harness and mechanical oracle
against planted behaviors. They do not measure a hosted model's reliability.
Most defects deliberately share the correct baseline answer; therefore the
static comparator sees only stale-cache failures. Interventions expose the
hidden failures by changing the decisive field, removing sole support, and
perturbing an irrelevant correlated field.

The four held-out templates exercise JSON arrays, quoted keys, nested records,
and domain-keyed contexts not used by the held-in template. The evaluator still
receives declared contract paths, and the generator and scorer remain
co-designed. This is shape-coverage evidence, not a claim of generalization or
independent benchmark validation.
