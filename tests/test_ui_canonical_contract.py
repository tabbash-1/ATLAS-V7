from pathlib import Path


def test_production_decision_ui_is_analyst_output_first():
    js=Path('atlas-production-decision.js').read_text()
    assert 'analyst_output' in js
    assert 'canonical_product_contract' in js
    assert '4-12H' in js
    assert 'ANALYSIS' in js
    assert 'live_execution' in js or 'liveExecution' in js


def test_product_shell_requires_final_gate_and_bound_analyst_output():
    js=Path('atlas-product-shell.js').read_text()
    assert "d.canonical_product_contract!=='analyst_output'" in js
    assert "c?.source_of_truth!=='FINAL_TRADE_GATE'" in js
    assert "a?.canonical_decision_id!==c.decision_id" in js
    assert "a?.decision_source_of_truth!=='FINAL_TRADE_GATE'" in js
    assert "a?.canonical_decision_schema!==c.schema" in js
    assert "a?.geometry_bound_to_canonical_decision!==true" in js
    assert "a?.horizon!=='4-12H'" in js
    assert "a?.analysis_only!==true" in js
    assert "a?.live_execution!==false" in js
    assert "productHorizon:'4-12H'" in js
    assert "evaluationHorizons:[4,8,12]" in js


def test_product_shell_fails_closed_to_wait():
    js=Path('atlas-product-shell.js').read_text()
    assert 'function failClosed()' in js
    assert "set('apsDecision','WAIT')" in js
    assert 'No analyst, legacy, AI, or geometry fallback may create a trade decision.' in js
    assert "failClosed:true" in js


def test_visible_geometry_comes_only_from_bound_analyst_output_when_ready():
    js=Path('atlas-product-shell.js').read_text()
    assert "ready=c.trade_ready===true&&a.analysis_ready===true&&norm(a.decision)===decision&&['LONG','SHORT'].includes(decision)" in js
    assert "set('apsEntry',ready?fmt(a.entry):'—')" in js
    assert "set('apsStop',ready?fmt(a.stop_loss):'—')" in js
    assert 'fmt(a.take_profit)' in js
    assert 'fmt(a.risk_reward,2)' in js
    assert 'trade_plan||{}' not in js
    assert 'p.entry' not in js
    assert 'p.stop_loss' not in js


def test_wait_state_surfaces_canonical_geometry_blockers():
    js=Path('atlas-product-shell.js').read_text()
    assert 'geometry_readiness' in js
    assert 'blocker_codes' in js
    assert 'Geometry blocker:' in js
    assert 'geometryReasonCodes:true' in js
    assert "set('apsAiGeometry',ready?" in js


def test_legacy_trade_plan_or_execution_flags_cannot_construct_product_shell_truth():
    js=Path('atlas-product-shell.js').read_text()
    forbidden=("p.status==='ACTIONABLE'", "return'ACTIONABLE'", "return'ARMED'", 'trade_plan||{}', 'execution_ready')
    for token in forbidden:
        assert token not in js


def test_decision_intelligence_is_shadow_only_and_cannot_override_canonical_decision():
    js=Path('atlas-product-shell.js').read_text()
    assert 'ATLAS_PRODUCT_SHELL_V7_BOUND_ANALYST_GEOMETRY' in js
    assert 'ATLAS AI · DECISION INTELLIGENCE' in js
    assert 'shadow context only' in js
    assert 'canonical decision unchanged' in js
    assert "set('apsAiBest',ready?decision:'WAIT')" in js
    assert 'ai?.canonical_action' not in js
    assert 'best_counterfactual' not in js
    assert 'decisionIntelligenceShadowOnly:true' in js


def test_product_shell_identity_is_analysis_only():
    js=Path('atlas-product-shell.js').read_text()
    assert 'ATLAS_PRODUCT_SHELL_V7_BOUND_ANALYST_GEOMETRY' in js
    assert 'CRYPTO TRADE INTELLIGENCE & ANALYSIS' in js
    assert '4–12H Analysis' in js
    assert 'Evidence quality' in js
    assert "analysisOnly:true" in js
    assert "liveExecution:false" in js
    assert "geometryReasonCodes:true" in js
