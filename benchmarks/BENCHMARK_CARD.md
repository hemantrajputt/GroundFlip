# EvidenceWireBench

EvidenceWireBench measures whether an evaluator can detect hidden evidence-wiring
defects that a correct unmodified answer conceals. It is a deterministic harness
test, not a general agent benchmark or hosted-model evaluation.

## Construction

Every case contains a seeded numeric fact, threshold, irrelevant but initially
correlated field, targeted flip, null ablation, and placebo flip. The expected
output is computed mechanically. No LLM writes or grades the oracle.

The benchmark constructs real nested JSON payloads and strict Draft 2020-12
schemas, then sends all three mutations through GroundFlip's production
intervention function. The full tier has 72 cases: 48 use a domain-object
template and 24 use four disjoint nested templates with arrays, quoted extension
keys, record matrices, and domain-keyed contexts. Those held-out templates test
the mutation/path stack on unseen fixture shapes; they do not establish model
generalization.

## Planted behaviors

- `grounded`: follows the decisive field, abstains without it, ignores placebo.
- `cached`: always repeats the initially correct answer.
- `stale_cache`: reads an older value, so the static baseline can catch it.
- `cross_wired`: follows the irrelevant correlated field.
- `distractor_sensitive`: uses both the correct and irrelevant fields.
- `unsupported_persistence`: follows updates but repeats a claim after sole
  support is removed.

## Metrics

The artifact reports static and intervention-based defect-detection
precision/recall, tracking, unsupported persistence, placebo stability, planted
dependency-edge recovery, measured schema-valid interventions, and mechanically
simulated synthesis-boundary observations.

## Limitations

The generator, behavior fixtures, and scorer are co-designed, so this suite
validates internal harness behavior rather than providing independent evidence.
The planted-edge metric tests black-box dependency localization, not source truth
or authority. Observation counts are not API calls. Hosted-model results must be
separate and name model snapshots, prompts, repetitions, dates, control churn,
token use, and cost.
