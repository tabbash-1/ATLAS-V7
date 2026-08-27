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
    assert 'syncProductionCommand' in js
    assert "setTimeout(run,1200)" in js


def test_command_strip_cannot_be_overwritten_by_legacy_research():
    js=Path('v7-ui-redesign.js').read_text()
    assert "['masterBadge','cmdMasterValue']" not in js
    assert "['tradeMgmtBadge','cmdPlanValue']" not in js
    html=Path('index.html').read_text()
    assert 'PRODUCTION DECISION' in html
    assert 'PRODUCTION PLAN' in html


def test_drift_monitor_retries_and_never_mislabels_transport_as_offline():
    js=Path('drift-monitor-ui.js').read_text()
    assert 'fetchJson' in js
    assert "badge.textContent='OFFLINE'" not in js
    assert 'MONITOR UNAVAILABLE' in js


def test_alerts_only_accept_actionable_production_rows():
    js=Path('confirmed-alerts-ui.js').read_text()
    assert "r.opportunity_state!=='ACTIONABLE'" in js
    assert '/api/production/paper-trades' in js
    assert '/api/alerts/evaluate' not in js
