from groundflip.benchmark import BEHAVIORS, evaluate_behavior, generate_cases, run_benchmark
from groundflip.jsonpath import get


def test_seeded_cases_are_reproducible_and_execute_real_nested_payloads():
    assert generate_cases("smoke", 7) == generate_cases("smoke", 7)
    cases = generate_cases("smoke", 7)
    assert len(cases) == 6
    assert {case.split for case in cases} == {"held_in", "held_out"}
    assert all(case.baseline_value < case.threshold < case.flipped_value for case in cases)
    assert all(get(case.payload, case.decisive_path) == case.baseline_value for case in cases)
    assert all(get(case.payload, case.distractor_path) == case.distractor_value for case in cases)
    assert any("[" in case.decisive_path for case in cases if case.split == "held_out")


def test_full_tier_has_four_held_out_templates_unseen_in_training_split():
    cases = generate_cases("full")
    held_in = {case.template for case in cases if case.split == "held_in"}
    held_out = {case.template for case in cases if case.split == "held_out"}
    assert held_in == {"domain_objects_v1"}
    assert len(held_out) == 4
    assert held_in.isdisjoint(held_out)


def test_stale_endpoint_coincidence_does_not_count_as_tracking():
    case = generate_cases("smoke")[0]
    row = evaluate_behavior(case, "stale_cache")
    assert row["baseline"] == row["targeted"] == "HIGH"
    assert not row["tracking_pass"]


def test_smoke_benchmark_exposes_hidden_defects_with_measured_mutations():
    result = run_benchmark("smoke")
    assert result["evaluations"] == 6 * len(BEHAVIORS)
    assert result["static_baseline"]["recall"] == 0.2
    assert result["groundflip"]["precision"] == 1
    assert result["groundflip"]["recall"] == 1
    assert result["held_out_nested_templates"]["groundflip"]["recall"] == 1
    assert result["incremental_defect_recall"] == 0.8
    assert result["interventions"]["attempted"] == result["evaluations"] * 3
    assert result["interventions"]["schema_valid"] == result["interventions"]["attempted"]
    assert result["interventions"]["validity_rate"] == 1
    assert result["simulated_synthesis_observations"]["single_contract_ratio"] == 2
