from pathlib import Path


def test_ranking_ui_is_manual_refresh_and_diagnostic_only():
    text = Path('atlas-opportunity-ranking-ui.js').read_text(encoding='utf-8')
    assert '/api/opportunities/ranked' in text
    assert 'readiness_score_is_probability!==false' in text
    assert 'production_decision_changed!==false' in text
    assert 'Readiness is a checklist score, not a win probability' in text
    assert "addEventListener('click',refresh)" in text
    assert 'setInterval(' not in text
    assert 'live_execution' not in text or 'Live execution remains off' in text


def test_render_boot_applies_ranking_ui_patch_before_runtime():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    patch = text.index('from opportunity_ranking_ui_boot_patch import apply as _apply_opportunity_ranking_ui_patch')
    run = text.index('runpy.run_path(str(BASE / "cloud_web_only_final.py"), run_name="__main__")')
    assert patch < run
    assert 'ATLAS_CLOUD_FORWARD_MIN_SCORE", "68"' in text
