from pathlib import Path

import pytest

from groundflip.contracts import contract_from_mapping, load_contract
from groundflip.models import ContractError, Relation


def base_contract():
    return {
        "version": 1,
        "name": "price",
        "scenario": "scenario.json",
        "target": {"kind": "action", "path": "$.decision"},
        "evidence": {"tool": "quote", "path": "$.price"},
        "mutation": {"op": "replace", "value": 12},
        "expect": {"relation": "changes_to", "value": "ESCALATE"},
        "controls": [{"target": "$.vendor", "relation": "invariant"}],
    }


def test_contract_mapping_is_typed_and_strict():
    contract = contract_from_mapping(base_contract())
    assert contract.expect.relation is Relation.CHANGES_TO
    assert contract.controls[0].expectation.relation is Relation.INVARIANT
    assert contract.runs == 5


@pytest.mark.parametrize(
    "edit",
    [
        {"version": 2},
        {"name": ""},
        {"runs": 0},
        {"target": {"path": "$..x"}},
        {"mutation": {"op": "swap"}},
        {"expect": {"relation": "magic"}},
    ],
)
def test_contract_rejects_bad_inputs(edit):
    raw = base_contract()
    raw.update(edit)
    with pytest.raises((ContractError, Exception)):
        contract_from_mapping(raw)


def test_relative_scenario_resolves_from_contract(tmp_path: Path):
    contract_path = tmp_path / "contract.yml"
    contract_path.write_text(
        """version: 1
name: x
scenario: scenario.json
target: {kind: claim, path: $.x}
evidence: {tool: t, path: $.x}
mutation: {op: replace, value: 2}
expect: {relation: tracks_value}
""",
        encoding="utf-8",
    )
    assert load_contract(contract_path).scenario == str((tmp_path / "scenario.json").resolve())
