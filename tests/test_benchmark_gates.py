from groundflip.benchmark import run_benchmark


def test_precommitted_offline_gates_pass_on_held_out_nested_templates():
    result = run_benchmark("full")
    assert result["interventions"]["validity_rate"] >= 0.95
    assert result["planted_edge_recovery"]["f1"] >= 0.85
    assert result["groundflip"]["precision"] >= 0.90
    assert result["groundflip"]["recall"] >= 0.80
    assert result["incremental_defect_recall"] >= 0.20
    assert result["held_out_nested_templates"]["groundflip"]["recall"] >= 0.80
    assert result["simulated_synthesis_observations"]["single_contract_ratio"] <= 3.0
