from pathlib import Path


def test_production_decision_ui_is_analyst_output_first():
    js=Path('atlas-production-decision.js').read_text()
    assert 'analyst_output' in js
    assert 'canonical_product_contract' in js
    assert '4-12H' in js
    assert 'ANALYSIS' in js
    assert 'live_execution' in js or 'liveExecution' in js


def test_product_shell_requires_canonical_analyst_output():
    js=Path('atlas-product-shell.js').read_text()
    assert "d.canonical_product_contract!=='analyst_output'" in js
    assert "a.horizon!=='4-12H'" in js
    assert "a.analysis_only!==true" in js
    assert "a.live_execution!==false" in js
    assert "canonicalContract:'analyst_output'" in js
    assert "productHorizon:'4-12H'" in js


def test_product_shell_fails_closed_to_wait():
    js=Path('atlas-product-shell.js').read_text()
    assert 'function failClosed()' in js
    assert "set('apsDecision','WAIT')" in js
    assert 'No legacy or AI fallback may create a decision.' in js
    assert "failClosed:true" in js


def test_visible_geometry_comes_only_from_analyst_output_when_ready():
    js=Path('atlas-product-shell.js').read_text()
    assert "ready=a.analysis_ready===true&&['LONG','SHORT'].includes(decision)" in js
    assert "set('apsEntry',ready?fmt(a.entry):'—')" in js
    assert "set('apsStop',ready?fmt(a.stop_loss):'—')" in js
    assert 'fmt(a.take_profit)' in js
    assert 'fmt(a.risk_reward,2)' in js


def test_wait_state_surfaces_canonical_geometry_blocker_codes():
    js=Path('atlas-product-shell.js').read_text()
    assert 'geometry_readiness' in js
    assert 'blocker_codes' in js
    assert 'Geometry blocker:' in js
    assert 'geometryReasonCodes:true' in js
    assert "set('apsAiGeometry',ready?" in js


def test_legacy_trade_plan_cannot_construct_product_shell_decision():
    js=Path('atlas-product-shell.js').read_text()
    forbidden=("p.status==='ACTIONABLE'", "return'ACTIONABLE'", "return'ARMED'", 'trade_plan||{}', 'execution_ready')
    for token in forbidden:
        assert token not in js


def test_ai_is_context_only_and_cannot_override_canonical_decision():
    js=Path('atlas-product-shell.js').read_text()
    assert 'Canonical decision cannot be overridden' in js
    assert 'CONTEXT ONLY · CANNOT OVERRIDE' in js
    assert "set('apsAiBest',a.analysis_ready?a.decision:'WAIT')" in js
    assert 'ai?.canonical_action' not in js
    assert 'best_counterfactual' not in js


def test_product_shell_identity_is_analysis_only():
    js=Path('atlas-product-shell.js').read_text()
    assert 'ATLAS_PRODUCT_SHELL_V4_ANALYST_OUTPUT_ONLY' in js
    assert 'CRYPTO TRADE INTELLIGENCE & ANALYSIS' in js
    assert 'Canonical 4–12H Analysis' in js
    assert 'Evidence quality' in js
    assert "analysisOnly:true" in js
    assert "liveExecution:false" in js
