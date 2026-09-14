from pathlib import Path


def test_cloud_web_only_installs_htf_v2_explicitly_before_quality_gate():
    text = Path('cloud_web_only.py').read_text(encoding='utf-8')

    required = [
        'from htf_structural_thesis import install as install_htf_structural_thesis',
        'HTF_STRUCTURAL_THESIS = install_htf_structural_thesis(atlas)',
        'from htf_price_action_overlay import install as install_htf_price_action',
        'HTF_PRICE_ACTION = install_htf_price_action(atlas)',
        'from htf_scenario_engine import install as install_htf_scenario_engine',
        'HTF_SCENARIO_ENGINE = install_htf_scenario_engine(atlas)',
        'from htf_sr_decision_v2 import install as install_htf_sr_decision_v2',
        'HTF_SR_DECISION_V2 = install_htf_sr_decision_v2(atlas)',
        "'htf_sr_decision_v2': HTF_SR_DECISION_V2",
    ]
    for marker in required:
        assert marker in text, marker

    canonical = text.index('CANONICAL_GEOMETRY = install_canonical_geometry(atlas)')
    structural = text.index('HTF_STRUCTURAL_THESIS = install_htf_structural_thesis(atlas)')
    price_action = text.index('HTF_PRICE_ACTION = install_htf_price_action(atlas)')
    scenario = text.index('HTF_SCENARIO_ENGINE = install_htf_scenario_engine(atlas)')
    sr_v2 = text.index('HTF_SR_DECISION_V2 = install_htf_sr_decision_v2(atlas)')
    quality = text.index('PRODUCT_QUALITY_GATE = install_product_quality_gate(atlas)')

    assert canonical < structural < price_action < scenario < sr_v2 < quality


def test_explicit_htf_v2_install_does_not_change_trading_threshold():
    text = Path('cloud_web_only.py').read_text(encoding='utf-8')
    assert "os.environ.setdefault('ATLAS_CLOUD_FORWARD_MIN_SCORE','68')" in text
