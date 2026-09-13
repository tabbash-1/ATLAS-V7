from atlas_decision_architecture import LayerResult, evaluate_staged_decision


def ok(state='OK'):
    return LayerResult(state=state, passed=True, confidence=0.8)


def test_all_mandatory_layers_plus_score_can_be_trade_ready():
    r = evaluate_staged_decision(candidate_direction='LONG', score=75, regime=ok('TREND_UP'), htf=ok('BULLISH'), flow=ok('BULLISH'), trigger_1h=ok('CONFIRMED'), cost_liquidity=ok('EDGE_AFTER_COST'), volatility_risk=ok('VALID'))
    assert r.trade_ready is True
    assert r.decision == 'LONG'
    assert r.source_of_truth == 'FINAL_TRADE_GATE'
    assert r.evaluation_horizons_h == (4, 8, 12)


def test_score_cannot_bypass_failed_flow():
    r = evaluate_staged_decision(candidate_direction='SHORT', score=99, regime=ok('TREND_DOWN'), htf=ok('BEARISH'), flow=LayerResult(state='CONFLICT', passed=False), trigger_1h=ok('CONFIRMED'), cost_liquidity=ok(), volatility_risk=ok())
    assert r.decision == 'WAIT'
    assert 'FLOW_CONFIRMATION' in r.blocking_gates


def test_stale_layer_fails_closed():
    stale = LayerResult(state='BULLISH', passed=True, freshness_ok=False)
    r = evaluate_staged_decision(candidate_direction='LONG', score=90, regime=ok(), htf=ok(), flow=stale, trigger_1h=ok(), cost_liquidity=ok(), volatility_risk=ok())
    assert r.trade_ready is False


def test_threshold_remains_68():
    r = evaluate_staged_decision(candidate_direction='LONG', score=67, regime=ok(), htf=ok(), flow=ok(), trigger_1h=ok(), cost_liquidity=ok(), volatility_risk=ok())
    assert r.decision == 'WAIT'
    assert r.production_threshold == 68


def test_invalid_direction_fails_closed():
    r = evaluate_staged_decision(candidate_direction='BUY', score=99, regime=ok(), htf=ok(), flow=ok(), trigger_1h=ok(), cost_liquidity=ok(), volatility_risk=ok())
    assert r.decision == 'WAIT'
    assert 'NO_DIRECTIONAL_CANDIDATE' in r.blocking_gates
