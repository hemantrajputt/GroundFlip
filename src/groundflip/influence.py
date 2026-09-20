"""Black-box claim/action to evidence-path influence mapping."""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .engine import ContractRunner
from .jsonpath import flatten_scalars
from .models import (
    Contract,
    EvidenceTarget,
    Expectation,
    Mutation,
    MutationOp,
    ObservationTarget,
    Relation,
    Scenario,
)


@dataclass(frozen=True)
class InfluenceProbe:
    tool: str
    path: str
    value: Any
    call_id: str | None = None


@dataclass(frozen=True)
class InfluenceEdge:
    tool: str
    path: str
    target_path: str
    original_value: Any
    mutated_value: Any
    effect_rate: float
    control_churn: float
    influential: bool
    status: str = "tested"
    error: str | None = None


@dataclass(frozen=True)
class InfluenceMap:
    scenario: str
    target_path: str
    edges: tuple[InfluenceEdge, ...]
    provider_calls: int
    runs_per_probe: int

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _sentinel(value: Any, identity: str) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        offset = int(hashlib.sha256(identity.encode()).hexdigest()[:6], 16) % 100_000 + 17
        return value + offset
    if isinstance(value, float):
        return value + max(abs(value) * 0.73, 17.0)
    if isinstance(value, str):
        return f"groundflip-{hashlib.sha256(identity.encode()).hexdigest()[:10]}"
    raise TypeError(f"No automatic scalar mutation for {type(value).__name__}")


def infer_probes(scenario: Scenario) -> list[InfluenceProbe]:
    probes: list[InfluenceProbe] = []
    for record in scenario.evidence:
        for path, value in flatten_scalars(record.structured_content):
            try:
                replacement = _sentinel(value, f"{record.tool}:{record.call_id}:{path}")
            except TypeError:
                continue
            probes.append(
                InfluenceProbe(
                    tool=record.tool,
                    call_id=record.call_id,
                    path=path,
                    value=replacement,
                )
            )
    return probes


def map_influence(
    scenario: Scenario,
    provider: Any,
    target_path: str,
    *,
    probes: Iterable[InfluenceProbe] | None = None,
    runs: int = 3,
    seed: int = 24601,
    min_effect: float = 0.50,
    noise_margin: float = 0.10,
) -> InfluenceMap:
    if not 0 <= min_effect <= 1 or not 0 <= noise_margin <= 1:
        raise ValueError("effect thresholds must be between 0 and 1")
    candidates = list(probes) if probes is not None else infer_probes(scenario)
    edges: list[InfluenceEdge] = []
    runner = ContractRunner(provider)
    for index, probe in enumerate(candidates):
        contract = Contract(
            version=1,
            name=f"influence-{index}",
            scenario="in-memory",
            target=ObservationTarget(kind="claim", path=target_path),
            evidence=EvidenceTarget(tool=probe.tool, path=probe.path, call_id=probe.call_id),
            mutation=Mutation(op=MutationOp.REPLACE, value=probe.value),
            expect=Expectation(relation=Relation.INVARIANT),
            runs=runs,
            seed=seed + index,
        )
        try:
            result = runner.run(contract, scenario)
            influential = (
                result.paired_effect >= min_effect
                and result.paired_effect > result.control_churn + noise_margin
            )
            edges.append(
                InfluenceEdge(
                    tool=probe.tool,
                    path=probe.path,
                    target_path=target_path,
                    original_value=result.original_value,
                    mutated_value=result.mutated_value,
                    effect_rate=result.paired_effect,
                    control_churn=result.control_churn,
                    influential=influential,
                )
            )
        except Exception as exc:
            edges.append(
                InfluenceEdge(
                    tool=probe.tool,
                    path=probe.path,
                    target_path=target_path,
                    original_value=None,
                    mutated_value=probe.value,
                    effect_rate=0,
                    control_churn=0,
                    influential=False,
                    status="skipped",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return InfluenceMap(
        scenario=scenario.name,
        target_path=target_path,
        edges=tuple(edges),
        provider_calls=len(candidates) * runs * 2,
        runs_per_probe=runs,
    )
