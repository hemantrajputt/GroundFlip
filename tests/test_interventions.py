import pytest

from groundflip.interventions import apply
from groundflip.models import InterventionError, Mutation, MutationOp

SCHEMA = {
    "type": "object",
    "properties": {"price": {"type": "number", "minimum": 0}, "label": {"type": "string"}},
    "required": ["label"],
    "additionalProperties": False,
}


def test_replace_add_delete_null_and_swap():
    document = {"price": 10, "label": "A"}
    assert apply(document, "$.price", Mutation(MutationOp.REPLACE, 20), SCHEMA).mutated_value == 20
    assert apply(document, "$.price", Mutation(MutationOp.ADD, 2), SCHEMA).mutated_value == 12
    assert "price" not in apply(document, "$.price", Mutation(MutationOp.DELETE), SCHEMA).document
    swapped = apply({"a": 1, "b": 2}, "$.a", Mutation(MutationOp.SWAP, other_path="$.b")).document
    assert swapped == {"a": 2, "b": 1}


def test_schema_invalid_and_noop_mutations_fail():
    with pytest.raises(InterventionError, match="schema"):
        apply({"price": 10, "label": "A"}, "$.price", Mutation(MutationOp.REPLACE, -1), SCHEMA)
    with pytest.raises(InterventionError, match="no-op"):
        apply({"price": 10}, "$.price", Mutation(MutationOp.REPLACE, 10))


def test_numeric_add_rejects_boolean():
    with pytest.raises(InterventionError):
        apply({"x": True}, "$.x", Mutation(MutationOp.ADD, 1))
