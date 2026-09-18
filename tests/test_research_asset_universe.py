from production_asset_universe import CANONICAL_PRODUCTION_ASSETS
from research_asset_universe import RESEARCH_ASSETS, RESEARCH_ONLY_ASSETS, safety_contract


def test_hype_is_research_only_not_production():
    assert "HYPEUSDT" in RESEARCH_ASSETS
    assert "HYPEUSDT" in RESEARCH_ONLY_ASSETS
    assert "HYPEUSDT" not in CANONICAL_PRODUCTION_ASSETS
    assert tuple(x for x in RESEARCH_ASSETS if x != "HYPEUSDT") == CANONICAL_PRODUCTION_ASSETS


def test_research_universe_is_fail_closed_against_production():
    c = safety_contract()
    assert c["research_only"] is True
    assert c["can_override_production"] is False
    assert c["changes_production_universe"] is False
    assert c["changes_score"] is False
    assert c["changes_threshold"] is False
    assert c["changes_geometry"] is False
    assert c["live_execution"] is False
