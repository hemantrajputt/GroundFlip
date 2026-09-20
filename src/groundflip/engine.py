"""Paired control/intervention experiment runner."""

from __future__ import annotations

import dataclasses
import random
from typing import Any

from .interventions import InterventionResult, apply
from .jsonpath import get
from .models import (
    BranchRun,
    Contract,
    ContractResult,
    Control,
    Expectation,
    InterventionError,
    MutationOp,
    Relation,
    Scenario,
    Verdict,
)
from .providers.base import SynthesisProvider
from .statistics import churn, wilson_interval
from .store import sha256_json

_MISSING = object()


def _matches(value: Any, expected: Any) -> bool:
    if isinstance(value, float) and isinstance(expected, (int, float)):
        return abs(value - float(expected)) <= max(1e-9, abs(float(expected)) * 1e-9)
    return value == expected


def _relation_pass(
    expectation: Expectation,
    control: Any,
    intervention: Any,
    mutated_evidence: Any,
) -> bool:
    relation = expectation.relation
    if relation is Relation.CHANGES_TO:
        expected = expectation.value if expectation.value is not None else mutated_evidence
        return intervention is not _MISSING and _matches(intervention, expected)
    if relation is Relation.TRACKS_VALUE:
        return intervention is not _MISSING and _matches(intervention, mutated_evidence)
    if relation in {Relation.INVARIANT, Relation.REJECTS_SOURCE}:
        return (
            control is not _MISSING
            and intervention is not _MISSING
            and _matches(intervention, control)
        )
    if relation is Relation.MONOTONIC_INCREASE:
        return (
            isinstance(control, (int, float))
            and not isinstance(control, bool)
            and isinstance(intervention, (int, float))
            and not isinstance(intervention, bool)
            and intervention > control
        )
    if relation is Relation.MONOTONIC_DECREASE:
        return (
            isinstance(control, (int, float))
            and not isinstance(control, bool)
            and isinstance(intervention, (int, float))
            and not isinstance(intervention, bool)
            and intervention < control
        )
    if relation is Relation.ABSTAINS:
        return intervention is _MISSING or intervention in expectation.abstention_values
    return False


def _observe(data: Any, path: str) -> Any:
    return get(data, path, default=_MISSING)


def _control_pass(control: Control, before: Any, after: Any, mutated_evidence: Any) -> bool:
    return _relation_pass(control.expectation, before, after, mutated_evidence)


class ContractRunner:
    def __init__(self, provider: SynthesisProvider) -> None:
        self.provider = provider

    @staticmethod
    def _intervene(scenario: Scenario, contract: Contract) -> tuple[Scenario, InterventionResult]:
        matches: list[int] = []
        primary_index: int | None = None
        for index, record in enumerate(scenario.evidence):
            direct = record.tool == contract.evidence.tool and (
                contract.evidence.call_id is None or record.call_id == contract.evidence.call_id
            )
            equivalent = bool(
                contract.evidence.equivalence_class
                and record.equivalence_class == contract.evidence.equivalence_class
            )
            if direct:
                primary_index = index
            if direct or equivalent:
                matches.append(index)
        if primary_index is None:
            raise InterventionError(
                f"No evidence matched tool={contract.evidence.tool!r} "
                f"call_id={contract.evidence.call_id!r}"
            )

        changed = list(scenario.evidence)
        primary_result: InterventionResult | None = None
        for index in matches:
            record = changed[index]
            result = apply(
                record.structured_content,
                contract.evidence.path,
                contract.mutation,
                schema=record.output_schema,
            )
            changed[index] = dataclasses.replace(record, structured_content=result.document)
            if index == primary_index:
                primary_result = result
        assert primary_result is not None
        return dataclasses.replace(scenario, evidence=tuple(changed)), primary_result

    def run(self, contract: Contract, scenario: Scenario) -> ContractResult:
        intervention_scenario, mutation = self._intervene(scenario, contract)
        rng = random.Random(contract.seed)
        branch_runs: list[BranchRun] = []

        for index in range(contract.runs):
            seed = rng.randrange(0, 2**31 - 1)
            order = ("control", "intervention")
            if rng.random() < 0.5:
                order = tuple(reversed(order))  # type: ignore[assignment]
            outputs: dict[str, Any] = {}
            for branch in order:
                snapshot = scenario if branch == "control" else intervention_scenario
                outputs[branch] = self.provider.synthesize(snapshot, seed=seed, branch=branch)

            control_output = outputs["control"]
            intervention_output = outputs["intervention"]
            target_control = _observe(control_output.data, contract.target.path)
            target_intervention = _observe(intervention_output.data, contract.target.path)
            target_pass = _relation_pass(
                contract.expect,
                target_control,
                target_intervention,
                mutation.mutated_value,
            )
            controls_pass = all(
                _control_pass(
                    item,
                    _observe(control_output.data, item.target.path),
                    _observe(intervention_output.data, item.target.path),
                    mutation.mutated_value,
                )
                for item in contract.controls
            )
            branch_runs.append(
                BranchRun(
                    index=index,
                    seed=seed,
                    order=order,
                    control=control_output,
                    intervention=intervention_output,
                    target_control=None if target_control is _MISSING else target_control,
                    target_intervention=(
                        None if target_intervention is _MISSING else target_intervention
                    ),
                    target_pass=target_pass,
                    controls_pass=controls_pass,
                )
            )

        target_successes = sum(run.target_pass for run in branch_runs)
        control_successes = sum(run.controls_pass for run in branch_runs)
        target_interval = wilson_interval(target_successes, len(branch_runs), contract.alpha)
        controls_interval = wilson_interval(control_successes, len(branch_runs), contract.alpha)
        control_churn = churn([run.target_control for run in branch_runs])
        changed_pairs = sum(
            not _matches(run.target_control, run.target_intervention) for run in branch_runs
        )
        paired_effect = changed_pairs / len(branch_runs)

        warnings: list[str] = []
        if not contract.evidence.sole_support and contract.expect.relation is Relation.ABSTAINS:
            warnings.append(
                "Abstention was requested without sole_support=true; duplicate support may exist."
            )
        if contract.mutation.op in {MutationOp.REPLACE, MutationOp.ADD, MutationOp.SWAP}:
            warnings.append(
                "This is a behavioral sensitivity probe; schema validity does not make the "
                "counterfactual a possible real-world state."
            )

        if control_churn > contract.max_control_churn:
            verdict = Verdict.INCONCLUSIVE
            warnings.append(
                f"Identical-control churn {control_churn:.3f} exceeds "
                f"{contract.max_control_churn:.3f}."
            )
        elif target_successes == len(branch_runs) and control_successes == len(branch_runs):
            verdict = Verdict.PASS
        elif (
            target_interval.upper < contract.min_pass_rate
            or controls_interval.upper < contract.min_pass_rate
        ):
            verdict = Verdict.FAIL
        elif (
            target_interval.estimate >= contract.min_pass_rate
            and controls_interval.estimate >= contract.min_pass_rate
        ):
            verdict = Verdict.PASS
        else:
            verdict = Verdict.INCONCLUSIVE

        hashes = {
            # Hash the complete executable contract. Omitting controls, thresholds,
            # replication count, or seed would let materially different tests share
            # an identity.
            "contract": sha256_json(dataclasses.asdict(contract)),
            "control_snapshot": sha256_json(dataclasses.asdict(scenario), apply_redaction=True),
            "intervention_snapshot": sha256_json(
                dataclasses.asdict(intervention_scenario), apply_redaction=True
            ),
        }
        return ContractResult(
            contract_name=contract.name,
            scenario_name=scenario.name,
            verdict=verdict,
            relation=contract.expect.relation.value,
            target_path=contract.target.path,
            evidence_tool=contract.evidence.tool,
            evidence_path=contract.evidence.path,
            original_value=mutation.original_value,
            mutated_value=mutation.mutated_value,
            runs=tuple(branch_runs),
            target_success=target_interval,
            controls_success=controls_interval,
            control_churn=control_churn,
            paired_effect=paired_effect,
            hashes=hashes,
            warnings=tuple(warnings),
        )
