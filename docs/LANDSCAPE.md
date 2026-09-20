# Landscape and novelty boundary

Scan date: 2026-08-07. This document records why GroundFlip has a narrow product
claim rather than calling every trace feature novel.

## Already solved elsewhere

- [MCP Inspector](https://github.com/modelcontextprotocol/inspector) interactively
  tests and debugs tools, resources, prompts, and transports.
- [MCP Observatory](https://github.com/KryptosAI/mcp-observatory) records,
  replays, diffs, and verifies MCP server cassettes.
- [Waza](https://github.com/microsoft/waza) evaluates agent skills, records
  snapshots, replays them, and ships adversarial/fault-injection packs.
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
  define interoperable agent, model, and tool spans and evaluation events.
- [OpenInference](https://github.com/Arize-ai/openinference) supplies an
  OpenTelemetry-compatible tracing convention and framework instrumentations.
- [Causal Agent Replay](https://arxiv.org/abs/2606.08275) applies do-style
  interventions to trajectory steps and estimates stochastic outcome effects and
  Shapley attribution.
- [ProvenanceGuard](https://arxiv.org/abs/2606.18037) performs source-aware claim
  verification over MCP traces and detects cross-source conflation.
- [AgentAssay](https://arxiv.org/abs/2603.02601) covers mutation testing,
  metamorphic relations, stochastic verdicts, and behavioral fingerprints.
- The `mcpact` package already uses “contract testing” for MCP servers.

Generic trace/replay, provenance checking, mutation testing, and MCP contracts
are therefore not GroundFlip's novelty claim.

## The remaining product gap

GroundFlip tests a different unit:

> Does claim or action path **Y** behaviorally obey MCP evidence path **X** under
> a declared relation, while unrelated path **Z** remains a placebo?

It combines:

1. wire-level MCP result capture;
2. schema-valid, path-specific evidence interventions;
3. repeated paired synthesis with an identical-control noise floor;
4. exact claim/action relational oracles;
5. influence maps and executable CI contracts;
6. a portable integrity certificate of what was tested.

This is closer to dataflow/taint contract testing for stochastic agents than to a
trace viewer or final-answer grader.

## Safe wording

Use:

> GroundFlip is an open-source MCP-native causal contract tester that combines
> wire-level evidence interventions, stochastic relational assertions over
> claims/actions, and portable test certificates.

Do not use:

- “first counterfactual agent replay”;
- “proves the model's internal reasoning”;
- “proves source truth”;
- “deterministic hosted-model replay”;
- “model-agnostic” before multi-provider live evidence exists.

## Relationship to harness engineering

Lilian Weng's [Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness/)
argues that harnesses themselves become optimization targets, while weak
evaluators and reward hacking remain central risks. GroundFlip is the evaluator
outside that loop: it supplies held-out, evidence-sensitive contracts that a
prompt or workflow optimizer should not be allowed to rewrite.

