"""Typed public models for evidence contracts and experiment results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class GroundFlipError(Exception):
    """Base exception for expected product errors."""


class ContractError(GroundFlipError):
    """Raised when a contract is invalid."""


class InterventionError(GroundFlipError):
    """Raised when an evidence intervention is invalid or unsafe."""


class ProviderError(GroundFlipError):
    """Raised when a synthesis provider cannot return a usable observation."""


class Relation(StrEnum):
    CHANGES_TO = "changes_to"
    TRACKS_VALUE = "tracks_value"
    INVARIANT = "invariant"
    MONOTONIC_INCREASE = "monotonic_increase"
    MONOTONIC_DECREASE = "monotonic_decrease"
    ABSTAINS = "abstains"
    REJECTS_SOURCE = "rejects_source"


class MutationOp(StrEnum):
    REPLACE = "replace"
    DELETE = "delete"
    NULL = "null"
    ADD = "add"
    SWAP = "swap"


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"


@dataclass(frozen=True)
class EvidenceTarget:
    tool: str
    path: str
    call_id: str | None = None
    source_type: str = "mcp"
    sole_support: bool = False
    equivalence_class: str | None = None


@dataclass(frozen=True)
class ObservationTarget:
    kind: str
    path: str
    label: str | None = None


@dataclass(frozen=True)
class Mutation:
    op: MutationOp
    value: Any = None
    other_path: str | None = None


@dataclass(frozen=True)
class Expectation:
    relation: Relation
    value: Any = None
    abstention_values: tuple[Any, ...] = (None, "UNKNOWN", "ABSTAIN", "ESCALATE")


@dataclass(frozen=True)
class Control:
    target: ObservationTarget
    expectation: Expectation


@dataclass(frozen=True)
class Contract:
    version: int
    name: str
    scenario: str
    target: ObservationTarget
    evidence: EvidenceTarget
    mutation: Mutation
    expect: Expectation
    controls: tuple[Control, ...] = ()
    runs: int = 5
    alpha: float = 0.05
    max_control_churn: float = 0.15
    min_pass_rate: float = 0.80
    seed: int = 1729


@dataclass(frozen=True)
class EvidenceRecord:
    tool: str
    structured_content: Any
    call_id: str | None = None
    output_schema: Mapping[str, Any] | None = None
    source_type: str = "mcp"
    equivalence_class: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    name: str
    prompt: str
    instructions: str
    evidence: tuple[EvidenceRecord, ...]
    output_schema: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    scripted: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderOutput:
    data: Mapping[str, Any]
    raw_text: str
    provider: str
    model: str
    latency_ms: float = 0.0
    usage: Mapping[str, int | float] = field(default_factory=dict)
    response_id: str | None = None


@dataclass(frozen=True)
class BranchRun:
    index: int
    seed: int
    order: tuple[str, str]
    control: ProviderOutput
    intervention: ProviderOutput
    target_control: Any
    target_intervention: Any
    target_pass: bool
    controls_pass: bool
    error: str | None = None


@dataclass(frozen=True)
class Interval:
    estimate: float
    lower: float
    upper: float
    confidence: float


@dataclass(frozen=True)
class ContractResult:
    contract_name: str
    scenario_name: str
    verdict: Verdict
    relation: str
    target_path: str
    evidence_tool: str
    evidence_path: str
    original_value: Any
    mutated_value: Any
    runs: tuple[BranchRun, ...]
    target_success: Interval
    controls_success: Interval
    control_churn: float
    paired_effect: float
    hashes: Mapping[str, str]
    warnings: tuple[str, ...] = ()
    schema_version: str = "groundflip.result/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["verdict"] = self.verdict.value
        return value
