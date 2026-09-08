from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_product_shell_does_not_fetch_or_publish_production_decision():
    src = text('atlas-product-shell.js')
    assert '/api/decision/current' not in src
    assert 'window.ATLAS_PRODUCTION_DECISION=' not in src
    assert 'window.ATLAS_PRODUCTION_SNAPSHOT_GUARD' in src
    assert 'g?.current?.()' in src or 'ATLAS_PRODUCTION_SNAPSHOT_GUARD?.current?.()' in src
    assert 'norm(g?.symbol?.())===currentSymbol()' in src


def test_product_shell_binds_geometry_to_canonical_final_gate_snapshot():
    src = text('atlas-product-shell.js')
    assert "c?.schema!=='ATLAS_CANONICAL_DECISION_TRUTH_V1'" in src
    assert "c?.source_of_truth!=='FINAL_TRADE_GATE'" in src
    assert "c?.product_horizon!=='4-12H'" in src
    assert "c.evaluation_horizons_h.join(',')!=='4,8,12'" in src
    assert 'a?.canonical_decision_id!==c.decision_id' in src
    assert "a?.decision_source_of_truth!=='FINAL_TRADE_GATE'" in src
    assert 'a?.canonical_decision_schema!==c.schema' in src
    assert 'a?.geometry_bound_to_canonical_decision!==true' in src
    assert 'a?.analysis_only!==true' in src
    assert 'a?.live_execution!==false' in src
    assert 'function failClosed()' in src
    assert "set('apsDecision','WAIT')" in src
    assert 'execution_ready' not in src
    assert "p.status==='ACTIONABLE'" not in src
    assert 'trade_plan||{}' not in src


def test_unified_terminal_is_final_gate_only_and_wait_hides_candidate_direction():
    src = text('atlas-unified-terminal.js')
    assert "ATLAS_UNIFIED_TERMINAL_V5_STRICT_FINAL_GATE" in src
    assert "const PRODUCT_FRAMES=['1d','12h','4h','1h']" in src
    assert "['1d','12h','6h','4h','1h']" not in src
    assert 'p.product_direction||p.candidate_direction' not in src
    assert 'p.trade_plan' not in src
    assert "$('auDir').textContent=actionable?decision:'—'" in src
    assert "a?.canonical_decision_id!==c.decision_id" in src
    assert "a?.decision_source_of_truth!=='FINAL_TRADE_GATE'" in src


def test_paper_ui_consumes_only_canonical_outcome_summary():
    src = text('atlas-paper-portfolio-ui.js')
    assert '/api/outcomes/summary?scope=signals&horizon=12' in src
    assert '/api/research/paper-portfolio-10k' not in src
    assert 'Prospective analyst_output LONG/SHORT' not in src
    assert "d.decision_source_of_truth!=='FINAL_TRADE_GATE'" in src
    assert "d.evaluation_horizons_h.join(',')!=='4,8,12'" in src
    assert "d.legacy_backfill_allowed!==false" in src
    assert 'CANONICAL_SIGNAL_COUNT_MISMATCH' in src


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


if __name__ == '__main__':
    test_product_shell_does_not_fetch_or_publish_production_decision()
    test_product_shell_binds_geometry_to_canonical_final_gate_snapshot()
    test_unified_terminal_is_final_gate_only_and_wait_hides_candidate_direction()
    test_paper_ui_consumes_only_canonical_outcome_summary()
    test_production_decision_rejects_stale_responses()
    test_snapshot_guard_is_the_only_acceptance_surface()
    print('production single snapshot authority tests: ok')
