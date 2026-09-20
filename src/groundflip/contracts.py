"""Strict loading and validation for the GroundFlip YAML contract DSL."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .jsonpath import parse
from .models import (
    Contract,
    ContractError,
    Control,
    EvidenceTarget,
    Expectation,
    Mutation,
    MutationOp,
    ObservationTarget,
    Relation,
)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be a mapping")
    return value


def _target(value: Any, name: str = "target") -> ObservationTarget:
    raw = _mapping(value, name)
    kind = str(raw.get("kind", "claim"))
    if kind not in {"claim", "action"}:
        raise ContractError(f"{name}.kind must be 'claim' or 'action'")
    path = str(raw.get("path", ""))
    parse(path)
    return ObservationTarget(kind=kind, path=path, label=raw.get("label"))


def _expectation(value: Any, name: str = "expect") -> Expectation:
    raw = _mapping(value, name)
    try:
        relation = Relation(str(raw.get("relation")))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in Relation)
        raise ContractError(f"{name}.relation must be one of: {allowed}") from exc
    abstentions = raw.get("abstention_values", (None, "UNKNOWN", "ABSTAIN", "ESCALATE"))
    if not isinstance(abstentions, (list, tuple)):
        raise ContractError(f"{name}.abstention_values must be a list")
    return Expectation(
        relation=relation,
        value=raw.get("value"),
        abstention_values=tuple(abstentions),
    )


def contract_from_mapping(raw_value: Any) -> Contract:
    raw = _mapping(raw_value, "contract")
    if int(raw.get("version", 0)) != 1:
        raise ContractError("Only contract version 1 is supported")
    name = str(raw.get("name", "")).strip()
    scenario = str(raw.get("scenario", "")).strip()
    if not name or not scenario:
        raise ContractError("contract name and scenario are required")

    evidence_raw = _mapping(raw.get("evidence"), "evidence")
    tool = str(evidence_raw.get("tool", "")).strip()
    evidence_path = str(evidence_raw.get("path", ""))
    if not tool:
        raise ContractError("evidence.tool is required")
    parse(evidence_path)
    evidence = EvidenceTarget(
        tool=tool,
        path=evidence_path,
        call_id=evidence_raw.get("call_id"),
        source_type=str(evidence_raw.get("source_type", "mcp")),
        sole_support=bool(evidence_raw.get("sole_support", False)),
        equivalence_class=evidence_raw.get("equivalence_class"),
    )

    mutation_raw = _mapping(raw.get("mutation"), "mutation")
    try:
        mutation_op = MutationOp(str(mutation_raw.get("op")))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in MutationOp)
        raise ContractError(f"mutation.op must be one of: {allowed}") from exc
    mutation = Mutation(
        op=mutation_op,
        value=mutation_raw.get("value"),
        other_path=mutation_raw.get("other_path"),
    )
    if mutation.op is MutationOp.SWAP and not mutation.other_path:
        raise ContractError("mutation.other_path is required for swap")
    if mutation.other_path:
        parse(str(mutation.other_path))

    controls: list[Control] = []
    for index, item in enumerate(raw.get("controls", [])):
        control_raw = _mapping(item, f"controls[{index}]")
        target_value = control_raw.get("target")
        if isinstance(target_value, str):
            target_value = {"kind": "claim", "path": target_value}
        expectation_value = control_raw.get("expect", control_raw)
        controls.append(
            Control(
                target=_target(target_value, f"controls[{index}].target"),
                expectation=_expectation(expectation_value, f"controls[{index}].expect"),
            )
        )

    runs = int(raw.get("runs", 5))
    alpha = float(raw.get("alpha", 0.05))
    max_churn = float(raw.get("max_control_churn", 0.15))
    min_pass_rate = float(raw.get("min_pass_rate", 0.80))
    if not 1 <= runs <= 100:
        raise ContractError("runs must be between 1 and 100")
    if not 0 < alpha < 1:
        raise ContractError("alpha must be between 0 and 1")
    if not 0 <= max_churn <= 1 or not 0 < min_pass_rate <= 1:
        raise ContractError("rate thresholds must be between 0 and 1")

    return Contract(
        version=1,
        name=name,
        scenario=scenario,
        target=_target(raw.get("target")),
        evidence=evidence,
        mutation=mutation,
        expect=_expectation(raw.get("expect")),
        controls=tuple(controls),
        runs=runs,
        alpha=alpha,
        max_control_churn=max_churn,
        min_pass_rate=min_pass_rate,
        seed=int(raw.get("seed", 1729)),
    )


def load_contract(path: str | Path) -> Contract:
    contract_path = Path(path)
    text = contract_path.read_text(encoding="utf-8")
    try:
        raw = json.loads(text) if contract_path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ContractError(f"Could not parse {contract_path}: {exc}") from exc
    contract = contract_from_mapping(raw)
    scenario_path = Path(contract.scenario)
    if not scenario_path.is_absolute():
        scenario_path = (contract_path.parent / scenario_path).resolve()
    return Contract(**{**contract.__dict__, "scenario": str(scenario_path)})
