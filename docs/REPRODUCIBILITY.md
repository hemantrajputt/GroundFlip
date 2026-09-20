# Reproducibility

## Offline evidence

Environment used for the checked-in result:

- date: 2026-08-07;
- Python: 3.13.7;
- OS: Windows;
- benchmark seed: `20260807`;
- tier: `full`;
- cases: 72 (48 held-in, 24 across four held-out nested templates);
- behaviors per case: 6;
- total evaluations: 432;
- schema-validated intervention attempts: 1,296.

Reproduce from the repository root:

```bash
pip install -e ".[dev]"
pytest
groundflip benchmark --tier full --seed 20260807 \
  --out benchmarks/results/offline-full.json
```

Expected result artifact SHA-256:

```text
92c17a806672d72cd81711da36e262d1d2e894179882e9a8c2680db510825e4e
```

The JSON contains every generated payload, strict schema, evaluation row, and
aggregate—not only percentages. See
[OFFLINE_RESULTS.md](../benchmarks/OFFLINE_RESULTS.md).

## Live-model evidence

No `OPENAI_API_KEY` was present in the build environment, so no hosted-model
metric is merged into the offline result or claimed in the CV. To run a live
smoke test:

```powershell
$env:OPENAI_API_KEY = "..."
$env:GROUNDFLIP_OPENAI_MODEL = "gpt-5.6-terra"
groundflip demo --provider openai --runs 5 --out .groundflip/live-demo
```

Before publishing live results, record:

- exact model alias/snapshot and provider;
- UTC date;
- prompt/scenario/contract hashes;
- run count and branch randomization seed;
- control churn and PASS/FAIL/INCONCLUSIVE counts;
- input/output tokens, latency, and cost;
- raw redacted result/certificate hashes.

Hosted models are stochastic and may change behind an alias. A live reproduction
is a new experiment, not a promise of bit-identical output.
