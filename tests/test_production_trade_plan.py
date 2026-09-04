import production_trade_plan as p


def base(**kw):
    d={'ok':True,'candidate_direction':'LONG','entry':100.0,'indicators':{'atr14':2.0},'production_signal_qualified':True,'execution_ready':True,'structural_geometry':{'obstacle_price':104.0,'obstacle_distance_pct':4.0,'continuation_strong':False,'breakout':{'confirmed':False}}}
    d.update(kw); return d


def test_actionable_now_has_complete_plan():
    x=p.build(base())
    assert x['status']=='ACTIONABLE' and x['entry_mode']=='NOW'
    assert x['stop_loss']<x['entry']<x['tp1']<x['tp2']
    assert x['rr_tp1']>=1 and x['rr_tp2']>=2
    assert x['can_execute'] is True
    assert x['live_execution'] is False
    assert x['execution_scope']=='DECISION_READY_ONLY_NO_ORDER_ROUTING'


def test_blocked_near_resistance_becomes_breakout_plan():
    d=base(execution_ready=False,production_signal_qualified=False,structural_geometry={'obstacle_price':101.0,'obstacle_distance_pct':1.0,'continuation_strong':True,'breakout':{'confirmed':False}})
    x=p.build(d)
    assert x['status']=='CONDITIONAL' and x['entry_mode']=='BREAKOUT'
    assert x['entry']>101.0 and x['stop_loss']<x['entry']<x['tp1']<x['tp2']
    assert x['can_execute'] is False


def test_qualified_but_geometry_blocked_never_gets_permission():
    x=p.build(base(execution_ready=False,production_signal_qualified=True))
    assert x['status']=='CONDITIONAL'
    assert x['can_execute'] is False
    assert x['live_execution'] is False


def test_geometry_ready_but_unqualified_never_gets_permission():
    x=p.build(base(execution_ready=True,production_signal_qualified=False))
    assert x['status']=='CONDITIONAL'
    assert x['can_execute'] is False
    assert x['live_execution'] is False


def test_conditional_long_clears_prior_24h_high_not_only_nearest_swing():
    d=base(execution_ready=False,production_signal_qualified=False,structural_geometry={
        'obstacle_price':100.7,'obstacle_distance_pct':0.7,'continuation_strong':False,
        'breakout':{'confirmed':False,'prior_24h_high':101.2,'prior_24h_low':97.0}})
    x=p.build(d)
    assert x['entry_mode']=='BREAKOUT'
    assert x['reference_structure']==101.2
    assert x['reference_structure_source']=='PRIOR_24H_HIGH'
    assert x['entry']>101.2


def test_conditional_short_clears_prior_24h_low_not_only_nearest_swing():
    d=base(candidate_direction='SHORT',entry=100.0,execution_ready=False,production_signal_qualified=False,structural_geometry={
        'obstacle_price':99.4,'obstacle_distance_pct':0.6,'continuation_strong':False,
        'breakout':{'confirmed':False,'prior_24h_high':103.0,'prior_24h_low':98.9}})
    x=p.build(d)
    assert x['entry_mode']=='BREAKOUT'
    assert x['reference_structure']==98.9
    assert x['reference_structure_source']=='PRIOR_24H_LOW'
    assert x['entry']<98.9


def test_far_24h_blocker_prefers_pullback_over_chasing_breakout():
    d=base(execution_ready=False,production_signal_qualified=False,structural_geometry={
        'obstacle_price':100.7,'obstacle_distance_pct':0.7,'continuation_strong':False,
        'breakout':{'confirmed':False,'prior_24h_high':103.0,'prior_24h_low':97.0}})
    x=p.build(d)
    assert x['entry_mode']=='PULLBACK' and x['entry']<100
    assert x['reference_structure']==103.0


def test_clear_room_wait_uses_pullback():
    d=base(execution_ready=False,production_signal_qualified=False,structural_geometry={'obstacle_price':106.0,'obstacle_distance_pct':6.0,'continuation_strong':False,'breakout':{'confirmed':False}})
    x=p.build(d)
    assert x['entry_mode']=='PULLBACK' and x['entry']<100


def test_short_ordering():
    d=base(candidate_direction='SHORT',entry=100.0,structural_geometry={'obstacle_price':94.0,'obstacle_distance_pct':6.0,'continuation_strong':False,'breakout':{'confirmed':False}})
    x=p.build(d)
    assert x['stop_loss']>x['entry']>x['tp1']>x['tp2']
    assert x['rr_tp1']>=1 and x['rr_tp2']>=2


def test_no_direction_does_not_invent_trade():
    x=p.build(base(candidate_direction=None,production_signal_qualified=False,execution_ready=False))
    assert x['status']=='WAIT' and x['entry_mode']=='NONE'
