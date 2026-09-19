from pathlib import Path


def test_production_snapshot_guard_rejects_stale_ui_responses():
    src = Path('production-web-autoload.js').read_text(encoding='utf-8')
    assert "let acceptedDecision=null,acceptedSymbol='',verifyEpoch=0;" in src
    assert 'epoch!==verifyEpoch' in src
    assert 'currentUiSymbol()!==symbol' in src
    assert 'restoreAcceptedSnapshot()' in src
    assert 'window.ATLAS_PRODUCTION_DECISION=acceptedDecision' in src


def test_asset_change_invalidates_previous_snapshot():
    src = Path('production-web-autoload.js').read_text(encoding='utf-8')
    assert 'verifyEpoch++;' in src
    assert 'acceptedDecision=null;' in src
    assert "acceptedSymbol='';" in src
