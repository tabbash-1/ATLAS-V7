from pathlib import Path


def test_cached_status_api_boots_after_background_interaction_runtime():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    runtime = text.index('from interaction_outcome_runtime import install as _install_interaction_outcome_runtime')
    status_api = text.index('from interaction_status_api import install as _install_interaction_status_api')
    entrypoint = text.index('entrypoint="atlas_research_runtime_server.py"')
    assert runtime < status_api < entrypoint
    block = text[status_api:entrypoint]
    assert '_install_interaction_status_api(_collector)' in block
    assert 'except Exception as _interaction_status_api_exc:' in block
    assert 'ATLAS interaction status API unavailable' in block


def test_status_api_boot_block_does_not_call_refresh_or_settlement():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    start = text.index('# Cached status endpoint only.')
    end = text.index('entrypoint="atlas_research_runtime_server.py"')
    block = text[start:end]
    assert 'interaction_outcome_refresh' not in block
    assert '_canonical_settlements' not in block
    assert 'trade_path_settlement' not in block
    assert 'production_decision =' not in block
    assert 'forward_observe =' not in block
