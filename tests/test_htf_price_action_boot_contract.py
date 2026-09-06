from pathlib import Path


def test_render_boot_installs_price_action_after_htf_and_before_quality_gate():
    text=Path('render_boot_patch.py').read_text(encoding='utf-8')
    assert 'HTF_PRICE_ACTION_BOOT_PATCH_V1' in text
    assert '_install_htf_structural_thesis(atlas)' in text
    assert '_install_htf_price_action(atlas)' in text
    assert text.index('_install_htf_structural_thesis(atlas)') < text.index('_install_htf_price_action(atlas)')


def test_overlay_contract_cannot_override_decision():
    text=Path('htf_price_action_overlay.py').read_text(encoding='utf-8')
    assert "'canonical_decision_override': False" in text
    assert "'forward_evidence_required_before_promotion': True" in text
    assert "'live_execution': False" in text
