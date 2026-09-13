from pathlib import Path


def test_render_boot_keeps_interaction_validation_out_of_web_process():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    start = text.index('if os.environ.get("RENDER"):')
    end = text.index('else:', start)
    block = text[start:end]

    assert 'interaction_outcome_runtime' not in block
    assert 'volatility_walkforward_runtime' not in block
    assert 'atlas_research_runtime_server.py' not in block
    assert 'cloud_production_canonical.py' in block


def test_render_boot_does_not_replace_production_or_forward_functions_for_research():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    start = text.index('if os.environ.get("RENDER"):')
    end = text.index('else:', start)
    block = text[start:end]

    assert 'production_decision =' not in block
    assert 'forward_observe =' not in block
    assert 'ATLAS_CLOUD_FORWARD_ENABLED"] = "0"' in block
    assert 'ATLAS_WEB_ONLY"] = "1"' in block
