# Contributing

GroundFlip is early-stage. Contributions should preserve its narrow contract:
test evidence dependence without overstating what black-box interventions prove.

## Setup

```bash
python -m venv .venv
pip install -e ".[dev]"
pytest
```

Run `ruff check src tests` and `python -m build` before opening a change.

## Change requirements

- Add a regression test for every bug fix.
- Keep the core importable without provider SDKs or credentials.
- Never add a secret, real customer trace, or unredacted model response.
- Preserve unknown JSON-RPC extension fields in the proxy.
- Use deterministic/mechanical benchmark oracles for supported typed claims.
- Label LLM-judge results as secondary diagnostics.
- Add held-out cases when changing intervention or mapping logic.
- Update the threat model when adding a new execution or trust boundary.
- Do not broaden “behavioral dependence” into claims about internal reasoning or
  real-world truth.

## Adding a provider

Implement the `SynthesisProvider` protocol and return structured `ProviderOutput`
metadata. Provider tests must use an injected fake client; live tests must be
marked `live`, skip without credentials, and never print keys or raw private data.

## Adding a relation

Document its mathematical/behavioral meaning, define an exact oracle, specify
what makes the verdict inconclusive, add positive/negative/property tests, and
include a planted benchmark behavior. A relation that only an LLM judge can grade
does not belong in the typed v0.1 core.

## Pull requests

Describe the problem, evidence, tests, security implications, and any claim that
must change. Small, reviewable patches are preferred. By contributing, you agree
that your contribution is licensed under Apache-2.0.

