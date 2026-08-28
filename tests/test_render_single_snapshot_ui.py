from pathlib import Path


def test_render_autoload_syncs_top_and_ai_from_same_snapshot():
    js = Path('production-web-autoload.js').read_text()
    assert 'function canonicalState(d)' in js
    assert 'function syncProductShell(d)' in js
    assert "setText('apsDecision', finalDecision)" in js
    assert "setText('apsAiBest', isActionable ?" in js
    assert "setText('apsEntry', isActionable ? fmt(p.entry) : '—')" in js
    assert "setText('apsTarget', isActionable ?" in js
    assert 'watchProductShellConsistency' in js
    assert 'window.ATLAS_SYNC_PRODUCT_SHELL = syncProductShell' in js


def test_actionable_requires_canonical_plan_and_execution_ready():
    js = Path('production-web-autoload.js').read_text()
    assert "p.status === 'ACTIONABLE' && qualified && ready" in js
    assert "const finalDecision = isActionable ? dir : 'WAIT'" in js
