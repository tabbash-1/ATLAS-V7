import horizon_fit_policy as h


def test_near_threshold_routes_to_swing_not_quick_without_breakout():
    x=h.classify(direction='LONG',score=65,threshold=68,votes=4,relative_volume=1.1,tactical_rr=1.2,breakout_confirmed=False,production_qualified=False,execution_ready=False)
    assert x['quick']['status']=='WATCH_ONLY'
    assert x['swing']['status']=='SWING_RESEARCH_WATCH'
    assert x['preferred_horizon']=='SWING_12_24H'
    assert x['production_threshold_changed'] is False


def test_quick_requires_strict_breakout_confirmation():
    x=h.classify(direction='SHORT',score=64,threshold=68,votes=4,relative_volume=.9,tactical_rr=1.1,breakout_confirmed=True,production_qualified=False,execution_ready=False)
    assert x['quick']['status']=='QUICK_TRADE_SHADOW'
    assert x['quick']['evaluation_horizons']==['1h','3h']
    assert x['quick']['can_override_production'] is False


def test_production_ready_remains_production_ready():
    x=h.classify(direction='LONG',score=72,threshold=68,votes=4,relative_volume=1.2,tactical_rr=1.4,breakout_confirmed=True,production_qualified=True,execution_ready=True)
    assert x['swing']['status']=='SWING_PRODUCTION_READY'
    assert x['preferred_horizon']=='SWING_12_24H'
    assert x['production_override_allowed'] is False


if __name__=='__main__':
    test_near_threshold_routes_to_swing_not_quick_without_breakout()
    test_quick_requires_strict_breakout_confirmation()
    test_production_ready_remains_production_ready()
    print('horizon fit policy tests: ok')
