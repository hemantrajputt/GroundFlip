from dataclasses import replace

from groundflip.demo import procurement_contracts, procurement_scenario
from groundflip.engine import ContractRunner
from groundflip.models import Verdict
from groundflip.providers.scripted import ScriptedProvider


def _result(contract_name: str, behavior: str):
    contract = next(item for item in procurement_contracts(runs=3) if item.name == contract_name)
    return ContractRunner(ScriptedProvider(behavior)).run(contract, procurement_scenario(behavior))


def test_grounded_agent_passes_all_demo_contracts():
    runner = ContractRunner(ScriptedProvider("grounded"))
    scenario = procurement_scenario("grounded")
    assert {runner.run(c, scenario).verdict for c in procurement_contracts(3)} == {Verdict.PASS}


def test_hidden_behaviors_are_exposed_by_relational_contracts():
    assert _result("price-controls-decision", "cached").verdict is Verdict.FAIL
    assert _result("marketing-score-is-placebo", "cross_wired").verdict is Verdict.FAIL
    assert (
        _result("missing-price-forces-escalation", "unsupported_persistence").verdict
        is Verdict.FAIL
    )


def test_identical_control_churn_for_scripted_provider_is_zero():
    result = _result("price-controls-decision", "grounded")
    assert result.control_churn == 0
    assert result.target_success.estimate == 1
    assert len(result.hashes["control_snapshot"]) == 64


def test_contract_hash_covers_execution_thresholds_and_replications():
    contract = next(iter(procurement_contracts(3)))
    runner = ContractRunner(ScriptedProvider("grounded"))
    baseline = runner.run(contract, procurement_scenario()).hashes["contract"]
    changed = runner.run(
        replace(contract, runs=4, min_pass_rate=0.95), procurement_scenario()
    ).hashes["contract"]
    assert baseline != changed


def test_inconclusive_when_control_branch_is_unstable():
    class AlternatingProvider(ScriptedProvider):
        def __init__(self):
            super().__init__("grounded")
            self.calls = 0

        def synthesize(self, scenario, *, seed, branch):
            output = super().synthesize(scenario, seed=seed, branch=branch)
            self.calls += 1
            if branch == "control" and self.calls % 4:
                data = {**output.data, "decision": "REJECT" if self.calls % 3 else "APPROVE"}
                return replace(output, data=data)
            return output

    contract = next(iter(procurement_contracts(5)))
    result = ContractRunner(AlternatingProvider()).run(contract, procurement_scenario())
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.control_churn > contract.max_control_churn
