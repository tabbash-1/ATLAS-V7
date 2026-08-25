from pathlib import Path


def test_interaction_runtime_boots_after_shadow_walkforward_and_is_failure_isolated():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    vol = text.index('from volatility_walkforward_runtime import install as _install_volatility_walkforward_runtime')
    interaction = text.index('from interaction_outcome_runtime import install as _install_interaction_outcome_runtime')
    entrypoint = text.index('entrypoint="atlas_research_runtime_server.py"')
    assert vol < interaction < entrypoint

    before = text[:interaction]
    assert before.rfind('try:') > vol
    after = text[interaction:entrypoint]
    assert '_install_interaction_outcome_runtime(_collector)' in after
    assert 'except Exception as _interaction_runtime_exc:' in after
    assert 'ATLAS interaction outcome runtime unavailable' in after


def test_boot_does_not_replace_production_or_forward_functions_for_interaction_runtime():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    block = text[
        text.index('# Outcome interaction validation is a separate background-only Research layer.'):
        text.index('entrypoint="atlas_research_runtime_server.py"')
    ]
    assert 'production_decision =' not in block
    assert 'forward_observe =' not in block
    assert '_install_interaction_outcome_runtime(_collector)' in block
