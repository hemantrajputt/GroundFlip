from groundflip.demo import procurement_scenario
from groundflip.influence import InfluenceProbe, map_influence
from groundflip.providers.scripted import ScriptedProvider

PROBES = [
    InfluenceProbe("procurement.get_quote", "$.price", 125000),
    InfluenceProbe("procurement.get_marketing", "$.approval_score", 7),
]


def test_influence_map_finds_decisive_not_placebo_field():
    result = map_influence(
        procurement_scenario("grounded"),
        ScriptedProvider("grounded"),
        "$.decision",
        probes=PROBES,
        runs=2,
    )
    assert [edge.influential for edge in result.edges] == [True, False]
    assert result.provider_calls == 8


def test_influence_map_exposes_cross_wiring():
    result = map_influence(
        procurement_scenario("cross_wired"),
        ScriptedProvider("cross_wired"),
        "$.decision",
        probes=PROBES,
        runs=2,
    )
    assert [edge.influential for edge in result.edges] == [False, True]
