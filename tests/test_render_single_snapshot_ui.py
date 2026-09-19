from pathlib import Path


def test_render_autoload_syncs_top_and_ai_from_same_snapshot():
    js = Path('production-web-autoload.js').read_text()
    assert 'function canonicalState(d)' in js
    assert 'function syncProductShell(d)' in js
    assert "setText('apsDecision',decision)" in js
    assert "setText('apsAiBest',decision)" in js
    assert "setText('apsEntry',actionable?fmt(a.entry):'—')" in js
    assert "setText('apsTarget',actionable?" in js
    assert 'watchProductShellConsistency' in js
    assert 'window.ATLAS_SYNC_PRODUCT_SHELL=syncProductShell' in js.replace(' ', '')


def test_actionable_requires_canonical_plan_and_execution_ready():
    js = Path('production-web-autoload.js').read_text()
    assert "ready=c?.trade_ready===true&&['LONG','SHORT'].includes(c?.decision)" in js
    assert "decision=actionable?c.decision:'WAIT'" in js
