import scenario_outcome_calibration as soc


def test_trigger_and_invalidation_order():
    rows = [
        {'symbol':'BTCUSDT','direction':'LONG','trigger_type':'BREAKOUT_RETEST','triggered':True,'triggered_at':'2026-09-06T10:00:00Z','invalidated':False,'forward_return_pct':{'4':1.0,'8':1.5,'12':2.0}},
        {'symbol':'ETHUSDT','direction':'SHORT','trigger_type':'FAILED_RETEST','triggered':True,'triggered_at':'2026-09-06T11:00:00Z','invalidated':True,'invalidated_at':'2026-09-06T12:00:00Z','forward_return_pct':{'4':-1.0,'8':-2.0,'12':-3.0}},
        {'symbol':'ZECUSDT','direction':'LONG','trigger_type':'LIQUIDITY_SWEEP','triggered':True,'triggered_at':'2026-09-06T12:00:00Z','invalidated':True,'invalidated_at':'2026-09-06T11:00:00Z','forward_return_pct':{'4':2.0}},
    ]
    out = soc.calibrate(rows, horizon=4)
    assert out['triggered'] == 2
    assert out['invalidated_before_trigger'] == 1
    assert out['overall_triggered']['wins'] == 2


def test_short_direction_is_normalized():
    rows = [{'symbol':'ETHUSDT','direction':'SHORT','trigger_type':'FAILED_RETEST','triggered':True,'forward_return_pct':{'8':-1.25}}]
    out = soc.calibrate(rows, horizon=8)
    assert out['overall_triggered']['avg_directional_return_pct'] == 1.25
    assert out['overall_triggered']['wins'] == 1


def test_safety_invariants():
    out = soc.calibrate([], horizon=12)
    assert out['research_only'] is True
    assert out['live_execution'] is False
    assert out['score_changed'] is False
    assert out['threshold_changed'] is False
    assert out['readiness_changed'] is False
    assert out['production_decision_changed'] is False
    assert out['recommendation']['auto_apply'] is False


def test_invalid_horizon_rejected():
    try:
        soc.calibrate([], horizon=24)
        raise AssertionError('expected ValueError')
    except ValueError:
        pass


if __name__ == '__main__':
    test_trigger_and_invalidation_order()
    test_short_direction_is_normalized()
    test_safety_invariants()
    test_invalid_horizon_rejected()
    print('scenario outcome calibration tests: OK')
