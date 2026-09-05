from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_horizon_overlay_exposes_one_primary_4_12h_product_lane():
    src = (ROOT / 'horizon_fit_overlay.py').read_text(encoding='utf-8')
    assert "PRODUCT_HORIZON = '4-12H'" in src
    assert "PRODUCT_LANE = 'CORE_4_12H'" in src
    assert "'role': 'PRIMARY_PRODUCT_LANE'" in src
    assert "matrix['core_4_12h'] = core" in src
    assert "row['preferred_horizon'] = PRODUCT_HORIZON" in src


def test_short_and_extended_lanes_are_context_only():
    src = (ROOT / 'horizon_fit_overlay.py').read_text(encoding='utf-8')
    assert "strict_quick['context_only'] = True" in src
    assert "swing['context_only'] = True" in src
    assert "strict_quick['can_override_production'] = False" in src
    assert "swing['can_override_production'] = False" in src


def test_product_is_analysis_only_and_never_live_execution():
    src = (ROOT / 'horizon_fit_overlay.py').read_text(encoding='utf-8')
    assert "row['analysis_only'] = True" in src
    assert "row['live_execution'] = False" in src
    assert "'live_execution': False" in src
