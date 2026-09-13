from pathlib import Path


def test_render_boot_stays_web_only_and_routes_through_canonical_launcher():
    text = Path('cloud_start.py').read_text(encoding='utf-8')

    render = text.index('if os.environ.get("RENDER"):')
    forward_off = text.index('os.environ["ATLAS_CLOUD_FORWARD_ENABLED"] = "0"')
    web_only = text.index('os.environ["ATLAS_WEB_ONLY"] = "1"')
    launcher = text.index('cloud_production_canonical.py')

    assert render < forward_off < web_only < launcher


def test_render_boot_does_not_reintroduce_interaction_or_settlement_workers():
    text = Path('cloud_start.py').read_text(encoding='utf-8')
    start = text.index('if os.environ.get("RENDER"):')
    end = text.index('else:', start)
    block = text[start:end]

    assert 'interaction_outcome_runtime' not in block
    assert 'interaction_outcome_refresh' not in block
    assert '_canonical_settlements' not in block
    assert 'trade_path_settlement' not in block
    assert 'production_decision =' not in block
    assert 'forward_observe =' not in block
