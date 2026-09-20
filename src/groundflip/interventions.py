"""Schema-checked evidence mutation primitives."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from . import jsonpath
from .models import InterventionError, Mutation, MutationOp


@dataclass(frozen=True)
class InterventionResult:
    document: Any
    original_value: Any
    mutated_value: Any
    path: str
    schema_valid: bool


def apply(
    document: Any,
    path: str,
    mutation: Mutation,
    schema: Mapping[str, Any] | None = None,
) -> InterventionResult:
    changed = copy.deepcopy(document)
    original = copy.deepcopy(jsonpath.get(changed, path))

    if mutation.op is MutationOp.REPLACE:
        jsonpath.set_value(changed, path, copy.deepcopy(mutation.value))
    elif mutation.op is MutationOp.NULL:
        jsonpath.set_value(changed, path, None)
    elif mutation.op is MutationOp.DELETE:
        jsonpath.delete(changed, path)
    elif mutation.op is MutationOp.ADD:
        if isinstance(original, bool) or not isinstance(original, (int, float)):
            raise InterventionError("add requires a numeric evidence value")
        if isinstance(mutation.value, bool) or not isinstance(mutation.value, (int, float)):
            raise InterventionError("add requires a numeric mutation.value")
        jsonpath.set_value(changed, path, original + mutation.value)
    elif mutation.op is MutationOp.SWAP:
        if not mutation.other_path:
            raise InterventionError("swap requires other_path")
        other = copy.deepcopy(jsonpath.get(changed, mutation.other_path))
        jsonpath.set_value(changed, mutation.other_path, copy.deepcopy(original))
        jsonpath.set_value(changed, path, other)
    else:  # pragma: no cover - Enum protects this boundary
        raise InterventionError(f"Unsupported mutation operation: {mutation.op}")

    if schema is not None:
        try:
            Draft202012Validator(schema).validate(changed)
        except ValidationError as exc:
            location = "/".join(str(item) for item in exc.absolute_path) or "$"
            raise InterventionError(
                f"Mutation violates the MCP output schema at {location}: {exc.message}"
            ) from exc

    mutated = jsonpath.get(changed, path, default=None)
    if mutation.op is not MutationOp.DELETE and original == mutated:
        raise InterventionError("Mutation is a no-op; choose a different value")
    return InterventionResult(
        document=changed,
        original_value=original,
        mutated_value=mutated,
        path=path,
        schema_valid=True,
    )
