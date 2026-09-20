"""EvidenceWireBench: generated ground truth for hidden evidence-wiring defects.

The offline suite is deliberately deterministic and judge-free. It validates
GroundFlip's mutation, observation, and scoring harness against planted behavior;
it is not evidence of hosted-model reliability.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .baseline import confusion, static_detects
from .interventions import apply
from .jsonpath import get
from .models import Mutation, MutationOp

BEHAVIORS = (
    "grounded",
    "cached",
    "stale_cache",
    "cross_wired",
    "distractor_sensitive",
    "unsupported_persistence",
)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    domain: str
    split: str
    template: str
    decisive_path: str
    distractor_path: str
    payload: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    baseline_value: int
    flipped_value: int
    stale_value: int
    distractor_value: int
    flipped_distractor: int
    threshold: int


def _infer_schema(value: Any) -> dict[str, Any]:
    """Build a strict fixture schema; numeric leaves allow null for ablation."""
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": ["integer", "null"]}
    if isinstance(value, float):
        return {"type": ["number", "null"]}
    if isinstance(value, str):
        return {"type": "string"}
    if value is None:
        return {"type": "null"}
    if isinstance(value, list):
        return {
            "type": "array",
            "prefixItems": [_infer_schema(item) for item in value],
            "items": False,
            "minItems": len(value),
            "maxItems": len(value),
        }
    if isinstance(value, Mapping):
        properties = {str(key): _infer_schema(item) for key, item in value.items()}
        return {
            "type": "object",
            "properties": properties,
            "required": sorted(properties),
            "additionalProperties": False,
        }
    raise TypeError(f"Unsupported benchmark fixture type: {type(value).__name__}")


def _payload_for(
    domain: str,
    split: str,
    index: int,
    baseline: int,
    distractor: int,
) -> tuple[str, dict[str, Any], str, str]:
    if split == "held_in":
        if domain == "commerce":
            return (
                "domain_objects_v1",
                {
                    "metrics": {"net_revenue": baseline},
                    "marketing": {"priority_score": distractor},
                },
                "$.metrics.net_revenue",
                "$.marketing.priority_score",
            )
        if domain == "incident":
            return (
                "domain_objects_v1",
                {
                    "telemetry": {"error_count": baseline},
                    "status": {"popularity": distractor},
                },
                "$.telemetry.error_count",
                "$.status.popularity",
            )
        return (
            "domain_objects_v1",
            {
                "stock": {"available_units": baseline},
                "catalog": {"feature_score": distractor},
            },
            "$.stock.available_units",
            "$.catalog.feature_score",
        )

    template = index % 4
    if template == 0:
        return (
            "ordered_signal_array_v2",
            {
                "snapshot": {
                    "payload": [
                        {"kind": "auxiliary", "reading": distractor},
                        {"kind": "decisive", "reading": baseline},
                    ],
                    "revision": "v2",
                }
            },
            "$.snapshot.payload[1].reading",
            "$.snapshot.payload[0].reading",
        )
    if template == 1:
        return (
            "quoted_extension_keys_v2",
            {
                "tool.result": {
                    "facts": {"primary-value": baseline, "noise.value": distractor}
                },
                "domain": domain,
            },
            "$['tool.result'].facts['primary-value']",
            "$['tool.result'].facts['noise.value']",
        )
    if template == 2:
        return (
            "record_matrix_v2",
            {
                "envelopes": [
                    {
                        "records": [
                            {"cells": [distractor, "auxiliary"]},
                            {"cells": [baseline, "decisive"]},
                        ]
                    }
                ]
            },
            "$.envelopes[0].records[1].cells[0]",
            "$.envelopes[0].records[0].cells[0]",
        )
    return (
        "domain_keyed_contexts_v2",
        {
            "contexts": [
                {"kind": "noise", "metrics": {domain: {"value": distractor}}},
                {"kind": "signal", "metrics": {domain: {"value": baseline}}},
            ]
        },
        f"$.contexts[1].metrics.{domain}.value",
        f"$.contexts[0].metrics.{domain}.value",
    )


def generate_cases(tier: str = "smoke", seed: int = 20260807) -> list[BenchmarkCase]:
    if tier not in {"smoke", "full"}:
        raise ValueError("tier must be 'smoke' or 'full'")
    count = 6 if tier == "smoke" else 72
    rng = random.Random(seed)
    domains = ("commerce", "incident", "inventory")
    cases: list[BenchmarkCase] = []
    for index in range(count):
        domain = domains[index % len(domains)]
        threshold = rng.randint(400_000, 800_000)
        baseline = threshold - rng.randint(40_001, 120_000)
        flipped = threshold + rng.randint(40_001, 120_000)
        stale = threshold + rng.randint(140_001, 220_000)
        distractor = baseline
        flipped_distractor = flipped
        split = "held_out" if index >= int(count * 2 / 3) else "held_in"
        template, payload, decisive_path, distractor_path = _payload_for(
            domain, split, index, baseline, distractor
        )
        cases.append(
            BenchmarkCase(
                case_id=f"{domain}-{index:03d}-{rng.randrange(16**8):08x}",
                domain=domain,
                split=split,
                template=template,
                decisive_path=decisive_path,
                distractor_path=distractor_path,
                payload=payload,
                output_schema=_infer_schema(payload),
                baseline_value=baseline,
                flipped_value=flipped,
                stale_value=stale,
                distractor_value=distractor,
                flipped_distractor=flipped_distractor,
                threshold=threshold,
            )
        )
    return cases


def _label(value: int | None, threshold: int) -> str:
    if value is None:
        return "ABSTAIN"
    return "HIGH" if value >= threshold else "LOW"


def _observed_value(case: BenchmarkCase, behavior: str, document: Mapping[str, Any]) -> int | None:
    decisive = get(document, case.decisive_path)
    distractor = get(document, case.distractor_path)
    if behavior == "cached":
        return case.baseline_value
    if behavior == "stale_cache":
        return case.stale_value
    if behavior == "cross_wired":
        return distractor
    if behavior == "distractor_sensitive":
        available = [item for item in (decisive, distractor) if item is not None]
        return max(available) if available else None
    if behavior == "unsupported_persistence" and decisive is None:
        return case.baseline_value
    return decisive


def _output(case: BenchmarkCase, behavior: str, document: Mapping[str, Any]) -> str:
    return _label(_observed_value(case, behavior, document), case.threshold)


def evaluate_behavior(case: BenchmarkCase, behavior: str) -> dict[str, Any]:
    if behavior not in BEHAVIORS:
        raise ValueError(f"Unknown behavior: {behavior}")

    targeted_result = apply(
        case.payload,
        case.decisive_path,
        Mutation(MutationOp.REPLACE, value=case.flipped_value),
        schema=case.output_schema,
    )
    ablation_result = apply(
        case.payload,
        case.decisive_path,
        Mutation(MutationOp.NULL),
        schema=case.output_schema,
    )
    placebo_result = apply(
        case.payload,
        case.distractor_path,
        Mutation(MutationOp.REPLACE, value=case.flipped_distractor),
        schema=case.output_schema,
    )
    interventions = (targeted_result, ablation_result, placebo_result)

    observations = {
        "baseline": _output(case, behavior, case.payload),
        "targeted": _output(case, behavior, targeted_result.document),
        "ablated": _output(case, behavior, ablation_result.document),
        "placebo": _output(case, behavior, placebo_result.document),
    }
    expected_baseline = _label(case.baseline_value, case.threshold)
    expected_flip = _label(case.flipped_value, case.threshold)

    if behavior in {"grounded", "unsupported_persistence"}:
        planted_paths = {case.decisive_path}
    elif behavior == "distractor_sensitive":
        planted_paths = {case.decisive_path, case.distractor_path}
    elif behavior == "cross_wired":
        planted_paths = {case.distractor_path}
    else:
        planted_paths = set()

    discovered_paths: set[str] = set()
    if observations["targeted"] != observations["baseline"]:
        discovered_paths.add(case.decisive_path)
    if observations["placebo"] != observations["baseline"]:
        discovered_paths.add(case.distractor_path)

    # Tracking is relational: the correct endpoint is insufficient if an already
    # wrong/stale control happened to have the same HIGH/LOW label.
    tracking_pass = (
        observations["baseline"] == expected_baseline
        and observations["targeted"] == expected_flip
        and observations["targeted"] != observations["baseline"]
    )
    ablation_pass = observations["ablated"] == "ABSTAIN"
    placebo_pass = observations["placebo"] == observations["baseline"]
    mapping_pass = discovered_paths == {case.decisive_path}
    causal_detected = not (tracking_pass and ablation_pass and placebo_pass and mapping_pass)
    static_detected = static_detects(observations["baseline"], expected_baseline)
    valid_interventions = sum(item.schema_valid for item in interventions)
    return {
        "case_id": case.case_id,
        "domain": case.domain,
        "split": case.split,
        "template": case.template,
        "behavior": behavior,
        "is_defect": behavior != "grounded",
        **observations,
        "expected_baseline": expected_baseline,
        "expected_targeted": expected_flip,
        "tracking_pass": tracking_pass,
        "ablation_pass": ablation_pass,
        "placebo_pass": placebo_pass,
        "discovered_paths": sorted(discovered_paths),
        "planted_paths": sorted(planted_paths),
        "expected_path": case.decisive_path,
        "mapping_pass": mapping_pass,
        "static_detected": static_detected,
        "causal_detected": causal_detected,
        "interventions_attempted": len(interventions),
        "interventions_schema_valid": valid_interventions,
        "static_observations": 1,
        "paired_contract_observations": 2,
        "full_suite_observations": len(observations),
    }


def _mapping_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, float | int]:
    tp = fp = fn = 0
    for row in rows:
        actual = set(row["planted_paths"])
        predicted = set(row["discovered_paths"])
        tp += len(actual & predicted)
        fp += len(predicted - actual)
        fn += len(actual - predicted)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _rates(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(rows) or 1
    return {
        "counterfactual_tracking_rate": sum(row["tracking_pass"] for row in rows) / total,
        "unsupported_persistence_rate": sum(not row["ablation_pass"] for row in rows) / total,
        "placebo_stability": sum(row["placebo_pass"] for row in rows) / total,
    }


def run_benchmark(tier: str = "smoke", seed: int = 20260807) -> dict[str, Any]:
    cases = generate_cases(tier=tier, seed=seed)
    rows = [evaluate_behavior(case, behavior) for case in cases for behavior in BEHAVIORS]
    defect_rows = [row for row in rows if row["is_defect"]]
    held_out = [row for row in rows if row["split"] == "held_out"]
    static = confusion(rows, "static_detected")
    causal = confusion(rows, "causal_detected")
    held_static = confusion(held_out, "static_detected")
    held_causal = confusion(held_out, "causal_detected")

    attempted = sum(row["interventions_attempted"] for row in rows)
    valid = sum(row["interventions_schema_valid"] for row in rows)
    static_observations = sum(row["static_observations"] for row in rows)
    paired_observations = sum(row["paired_contract_observations"] for row in rows)
    suite_observations = sum(row["full_suite_observations"] for row in rows)
    return {
        "schema_version": "evidencewirebench.result/v2",
        "tier": tier,
        "seed": seed,
        "cases": len(cases),
        "behaviors": len(BEHAVIORS),
        "evaluations": len(rows),
        "static_baseline": static,
        "groundflip": causal,
        "held_out_nested_templates": {
            "evaluations": len(held_out),
            "templates": sorted({row["template"] for row in held_out}),
            "static_baseline": held_static,
            "groundflip": held_causal,
        },
        "incremental_defect_recall": causal["recall"] - static["recall"],
        "objective_rates_all_behaviors": _rates(rows),
        "objective_rates_planted_defects": _rates(defect_rows),
        "planted_edge_recovery": _mapping_metrics(rows),
        "simulated_synthesis_observations": {
            "static": static_observations,
            "single_paired_contract": paired_observations,
            "full_three_intervention_suite": suite_observations,
            "single_contract_ratio": paired_observations / static_observations,
            "full_suite_ratio": suite_observations / static_observations,
        },
        "interventions": {
            "attempted": attempted,
            "schema_valid": valid,
            "validity_rate": valid / attempted if attempted else 0.0,
        },
        "rows": rows,
        "case_manifest": [asdict(case) for case in cases],
        "limitations": [
            "Offline benchmark uses planted deterministic behaviors, not a hosted model.",
            "Generator, behavior fixtures, and scorer are co-designed harness tests, not independent validation.",
            "Held-out templates exercise unseen nested payload shapes in the mutation stack; they do not prove model generalization.",
            "Observation counts are simulated synthesis boundaries, not billed API calls.",
            "Planted-edge recovery measures black-box dependency localization, not source truth or authority.",
            "Live-model metrics must be reported separately and never merged into this result.",
        ],
    }


def write_benchmark(path: str | Path, result: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
