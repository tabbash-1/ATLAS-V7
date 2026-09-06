import scenario_outcome_recorder as sor


def _c(t,o,h,l,c):
    return {'time':t,'open':o,'high':h,'low':l,'close':c,'closed':True}


def test_long_requires_close_then_retest_hold():
    rec={'direction':'LONG','trigger_level':100.0,'invalidation_level':90.0,'triggered':False,'invalidated':False}
    candles=[
        _c('2026-09-06T04:00:00+00:00',95,101,94,101),
        _c('2026-09-06T08:00:00+00:00',101,103,99,102),
    ]
    out=sor.settle(rec,candles)
    assert out['triggered'] is True
    assert out['activation_price']==102


def test_touch_without_close_does_not_trigger():
    rec={'direction':'LONG','trigger_level':100.0,'invalidation_level':90.0,'triggered':False,'invalidated':False}
    candles=[_c('2026-09-06T04:00:00+00:00',95,102,94,99)]
    out=sor.settle(rec,candles)
    assert out.get('triggered') is not True


def test_short_symmetric_trigger():
    rec={'direction':'SHORT','trigger_level':100.0,'invalidation_level':110.0,'triggered':False,'invalidated':False}
    candles=[
        _c('2026-09-06T04:00:00+00:00',105,106,98,99),
        _c('2026-09-06T08:00:00+00:00',99,101,96,98),
    ]
    out=sor.settle(rec,candles)
    assert out['triggered'] is True
    assert out['activation_price']==98


def test_invalidation_close_is_recorded():
    rec={'direction':'LONG','trigger_level':100.0,'invalidation_level':90.0,'triggered':False,'invalidated':False}
    out=sor.settle(rec,[_c('2026-09-06T04:00:00+00:00',92,93,88,89)])
    assert out['invalidated'] is True


def test_capture_preserves_research_only_contract():
    decision={'symbol':'BTCUSDT','htf_scenario_engine':{
        'version':'HTF_SCENARIO_ENGINE_V1','readiness':'CONDITIONAL_SCENARIO_READY','reason':'x',
        'selected_case':{'direction':'LONG','trigger_type':'BREAKOUT_RETEST_HOLD','trigger_level':100,'invalidation_level':90}}}
    out=sor.capture(decision,'2026-09-06T00:00:00+00:00')
    assert out['research_only'] is True
    assert out['live_execution'] is False
    assert out['triggered'] is False


def test_forward_return_is_raw_market_return_for_short():
    rec={'direction':'SHORT','triggered':True,'triggered_at':'2026-09-06T00:00:00+00:00','activation_price':100.0,'forward_return_pct':{}}
    candles=[
        _c('2026-09-06T04:00:00+00:00',100,101,94,95),
        _c('2026-09-06T08:00:00+00:00',95,96,89,90),
        _c('2026-09-06T12:00:00+00:00',90,91,84,85),
    ]
    out=sor.attach_forward_returns(rec,candles)
    assert out['forward_return_pct']['4'] == -5.0
    assert out['forward_return_pct']['8'] == -10.0
    assert out['forward_return_pct']['12'] == -15.0


if __name__=='__main__':
    test_long_requires_close_then_retest_hold()
    test_touch_without_close_does_not_trigger()
    test_short_symmetric_trigger()
    test_invalidation_close_is_recorded()
    test_capture_preserves_research_only_contract()
    test_forward_return_is_raw_market_return_for_short()
    print('scenario outcome recorder tests: OK')
