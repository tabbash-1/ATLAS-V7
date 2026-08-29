from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_product_shell_does_not_fetch_or_publish_production_decision():
    src = text('atlas-product-shell.js')
    refresh = src.split('async function refreshAi()', 1)[1].split('function update()', 1)[0]
    assert '/api/decision/current' not in refresh
    assert 'window.ATLAS_PRODUCTION_DECISION=pd' not in src
    assert 'ATLAS_PRODUCTION_SNAPSHOT_GUARD?.current?.()' in src
    assert 'acceptedSnapshotOnly:true' in src


def test_production_decision_rejects_stale_responses():
    src = text('atlas-production-decision.js')
    assert 'let verifyEpoch=0' in src
    assert 'requestEpoch!==verifyEpoch||currentSymbol()!==symbol' in src
    assert 'guard?.accept' in src
    assert 'staleResponseGuard:true' in src


def test_snapshot_guard_is_the_only_acceptance_surface():
    src = text('production-web-autoload.js')
    assert 'function acceptSnapshot' in src
    assert 'function invalidateSnapshot' in src
    assert 'accept:acceptSnapshot' in src
    assert 'invalidate:invalidateSnapshot' in src
