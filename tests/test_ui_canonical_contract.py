from pathlib import Path


def test_product_shell_sync_is_installed():
    js=Path('atlas-production-decision.js').read_text()
    assert 'syncProductShell' in js
    assert 'Verified Production plan' in js
    assert 'Conditional Production plan' in js
    assert "canonicalPlan:true" in js


def test_opportunity_scanner_is_production_only_and_fail_closed():
    js=Path('opportunity-scanner-ui.js').read_text()
    assert '/api/production/opportunities' in js
    assert "fallback_signals_allowed:false" in js
    assert "r.opportunity_state==='ACTIONABLE'" not in js or 'ENTER_LONG' in js
    assert 'opportunityScore(' not in js
    assert 'HYPEUSDT' in js


def test_alerts_only_accept_actionable_production_rows():
    js=Path('confirmed-alerts-ui.js').read_text()
    assert "r.opportunity_state!=='ACTIONABLE'" in js
    assert '/api/production/paper-trades' in js
    assert '/api/alerts/evaluate' not in js
