from pathlib import Path


def test_cloud_start_remains_untouched_by_staged_shadow_wiring():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    assert 'staged_shadow_api' not in text
    assert 'staged_decision_shadow' not in text
    assert 'ATLAS_CLOUD_FORWARD_MIN_SCORE", "68"' in text
    assert 'runpy.run_path(str(BASE / "cloud_production_canonical.py")' in text


def test_shadow_is_wired_through_existing_research_bootstrap():
    text = Path('committed_research_api.py').read_text(encoding='utf-8')
    assert 'install_staged_shadow_api' in text
    assert "'staged_shadow_api':staged_shadow_api" in text


def test_shadow_wiring_does_not_assign_production_decision():
    overlay = Path('staged_shadow_api_overlay.py').read_text(encoding='utf-8')
    assert 'atlas.production_decision =' not in overlay
    assert 'can_override_production": False' in overlay
