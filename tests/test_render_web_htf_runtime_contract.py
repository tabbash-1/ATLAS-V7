from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_web_entrypoint_installs_core_4_12h_authority_before_ai():
    web = (ROOT / 'cloud_start_web.py').read_text(encoding='utf-8')

    assert 'from htf_structural_thesis import install as _install_htf_structural_thesis' in web
    assert '_install_htf_structural_thesis(_collector)' in web
    assert 'from htf_price_action_overlay import install as _install_htf_price_action' in web
    assert '_install_htf_price_action(_collector)' in web
    assert 'from htf_scenario_engine import install as _install_htf_scenario_engine' in web
    assert '_install_htf_scenario_engine(_collector)' in web
    assert 'from product_quality_gate_overlay import install as _install_product_quality_gate' in web
    assert '_install_product_quality_gate(_collector)' in web

    htf = web.index('_install_htf_structural_thesis(_collector)')
    quality = web.index('_install_product_quality_gate(_collector)')
    ai = web.index('_install_ai_trade_council(_collector)')
    assert htf < quality < ai


def test_render_web_ui_does_not_present_tactical_1_3h_as_product_lane():
    web = (ROOT / 'cloud_start_web.py').read_text(encoding='utf-8')
    assert 'Core 4–12H + 1H entry confirmation' in web
    assert '<span>Core 4–12H</span>' in web
    assert '<span>1H Confirmation</span>' in web
