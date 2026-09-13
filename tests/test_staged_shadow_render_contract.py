from pathlib import Path


def test_render_entrypoint_keeps_final_guard_runtime_after_shadow_install():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    shadow = text.index('_install_staged_shadow_api')
    final_runtime = text.index('runpy.run_path(str(BASE / "cloud_web_only_final.py")')
    assert shadow < final_runtime
    assert 'ATLAS_CLOUD_FORWARD_MIN_SCORE", "68"' in text
    assert 'STAGED_SHADOW_API' in text


def test_shadow_wiring_does_not_assign_production_decision():
    overlay = Path('staged_shadow_api_overlay.py').read_text(encoding='utf-8')
    assert 'atlas.production_decision =' not in overlay
    assert 'can_override_production": False' in overlay
