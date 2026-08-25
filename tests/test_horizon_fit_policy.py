import horizon_fit_policy as h


def test_near_threshold_routes_to_neutral_swing_without_breakout():
    x=h.classify(symbol='XRPUSDT',direction='LONG',score=65,threshold=68,votes=4,relative_volume=1.1,tactical_rr=1.2,breakout_confirmed=False,production_qualified=False,execution_ready=False,obstacle_reason='VERY_CLOSE_PRIOR_STRUCTURE')
    assert x['quick']['status']=='WATCH_ONLY'
    assert x['swing']['status']=='SWING_RESEARCH_WATCH'
    assert x['swing']['swing_quality_tier']=='NEUTRAL'
    assert x['preferred_horizon']=='SWING_12_24H'
    assert x['production_threshold_changed'] is False
    assert x['production_score_adjustment'] == 0


def test_positive_combo_is_provisional_not_validated():
    x=h.classify(symbol='BTCUSDT',direction='LONG',score=65,threshold=68,votes=4,relative_volume=.5,tactical_rr=.8,breakout_confirmed=False,production_qualified=False,execution_ready=False,obstacle_reason='VERY_CLOSE')
    assert x['quick']['status']=='WATCH_ONLY'
    assert x['swing']['status']=='SWING_RESEARCH_PROVISIONAL_POSITIVE'
    assert x['swing']['swing_quality_tier']=='PROVISIONAL_POSITIVE'
    assert x['swing']['swing_quality_evidence']['independent_12h_n'] == 2
    assert x['swing']['independent_validation_complete'] is False
    assert x['swing']['minimum_independent_episodes_for_validated_tier'] == 5
    assert x['swing']['production_qualified'] is False
    assert x['swing']['can_override_production'] is False
    assert x['swing']['production_score_adjustment'] == 0
    assert x['production_threshold_changed'] is False
    assert x['production_score_adjustment'] == 0


def test_negative_combo_is_provisional_not_promoted():
    x=h.classify(symbol='HYPEUSDT',direction='SHORT',score=65,threshold=68,votes=4,relative_volume=.5,tactical_rr=.8,breakout_confirmed=False,production_qualified=False,execution_ready=False,obstacle_reason='VERY_CLOSE')
    assert x['swing']['status']=='SWING_RESEARCH_PROVISIONAL_NEGATIVE'
    assert x['swing']['swing_quality_tier']=='PROVISIONAL_NEGATIVE'
    assert x['swing']['swing_quality_evidence']['independent_12h_n'] == 2
    assert x['swing']['swing_quality_evidence']['mean_12h_pct'] < 0
    assert x['swing']['independent_validation_complete'] is False
    assert x['swing']['production_score_adjustment'] == 0
    assert x['production_override_allowed'] is False


def test_combo_priority_does_not_apply_below_research_band():
    x=h.classify(symbol='BTCUSDT',direction='LONG',score=59,threshold=68,votes=4,relative_volume=2,tactical_rr=3,breakout_confirmed=True,production_qualified=False,execution_ready=False,obstacle_reason='VERY_CLOSE')
    assert x['swing']['status']=='SWING_WATCH'
    assert x['swing']['swing_quality_tier']=='UNRATED'


def test_quick_requires_strict_breakout_confirmation():
    x=h.classify(symbol='XRPUSDT',direction='SHORT',score=64,threshold=68,votes=4,relative_volume=.9,tactical_rr=1.1,breakout_confirmed=True,production_qualified=False,execution_ready=False,obstacle_reason='VERY_CLOSE')
    assert x['quick']['status']=='QUICK_TRADE_SHADOW'
    assert x['quick']['evaluation_horizons']==['1h','3h']
    assert x['quick']['can_override_production'] is False


def test_production_ready_remains_production_ready():
    x=h.classify(symbol='BTCUSDT',direction='LONG',score=72,threshold=68,votes=4,relative_volume=1.2,tactical_rr=1.4,breakout_confirmed=True,production_qualified=True,execution_ready=True,obstacle_reason='VERY_CLOSE')
    assert x['swing']['status']=='SWING_PRODUCTION_READY'
    assert x['swing']['swing_quality_tier']=='PRODUCTION'
    assert x['preferred_horizon']=='SWING_12_24H'
    assert x['production_override_allowed'] is False
    assert x['production_score_adjustment'] == 0


if __name__=='__main__':
    test_near_threshold_routes_to_neutral_swing_without_breakout()
    test_positive_combo_is_provisional_not_validated()
    test_negative_combo_is_provisional_not_promoted()
    test_combo_priority_does_not_apply_below_research_band()
    test_quick_requires_strict_breakout_confirmation()
    test_production_ready_remains_production_ready()
    print('horizon fit policy tests: ok')
