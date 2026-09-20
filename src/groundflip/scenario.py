"""Scenario snapshots: the model-visible boundary GroundFlip branches from."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .models import ContractError, EvidenceRecord, Scenario


def scenario_from_mapping(raw_value: Any) -> Scenario:
    if not isinstance(raw_value, Mapping):
        raise ContractError("scenario must be a mapping")
    raw = raw_value
    name = str(raw.get("name", "")).strip()
    prompt = str(raw.get("prompt", "")).strip()
    instructions = str(raw.get("instructions", "")).strip()
    if not name or not prompt:
        raise ContractError("scenario name and prompt are required")

    output_schema = raw.get("output_schema")
    if not isinstance(output_schema, Mapping):
        raise ContractError("scenario.output_schema must be a JSON Schema mapping")
    try:
        Draft202012Validator.check_schema(output_schema)
    except SchemaError as exc:
        raise ContractError(f"scenario.output_schema is invalid: {exc.message}") from exc

    evidence: list[EvidenceRecord] = []
    raw_evidence = raw.get("evidence", [])
    if not isinstance(raw_evidence, list) or not raw_evidence:
        raise ContractError("scenario.evidence must be a non-empty list")
    for index, item in enumerate(raw_evidence):
        if not isinstance(item, Mapping):
            raise ContractError(f"scenario.evidence[{index}] must be a mapping")
        tool = str(item.get("tool", "")).strip()
        if not tool or "structured_content" not in item:
            raise ContractError(f"scenario.evidence[{index}] needs tool and structured_content")
        schema = item.get("output_schema")
        if schema is not None:
            if not isinstance(schema, Mapping):
                raise ContractError(f"scenario.evidence[{index}].output_schema must be a mapping")
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as exc:
                raise ContractError(
                    f"scenario.evidence[{index}].output_schema is invalid: {exc.message}"
                ) from exc
            try:
                Draft202012Validator(schema).validate(item["structured_content"])
            except ValidationError as exc:
                raise ContractError(
                    f"scenario.evidence[{index}] does not match its schema: {exc.message}"
                ) from exc
        evidence.append(
            EvidenceRecord(
                tool=tool,
                structured_content=item["structured_content"],
                call_id=item.get("call_id"),
                output_schema=schema,
                source_type=str(item.get("source_type", "mcp")),
                equivalence_class=item.get("equivalence_class"),
                metadata=item.get("metadata", {}),
            )
        )

    metadata = raw.get("metadata", {})
    scripted = raw.get("scripted", {})
    if not isinstance(metadata, Mapping) or not isinstance(scripted, Mapping):
        raise ContractError("scenario metadata and scripted fields must be mappings")
    return Scenario(
        name=name,
        prompt=prompt,
        instructions=instructions,
        evidence=tuple(evidence),
        output_schema=output_schema,
        metadata=metadata,
        scripted=scripted,
    )


def load_scenario(path: str | Path) -> Scenario:
    scenario_path = Path(path)
    try:
        raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Could not load scenario {scenario_path}: {exc}") from exc
    return scenario_from_mapping(raw)
