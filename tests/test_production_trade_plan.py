import production_trade_plan as p


def base(**kw):
    d={'ok':True,'candidate_direction':'LONG','entry':100.0,'indicators':{'atr14':2.0},'production_signal_qualified':True,'execution_ready':True,'structural_geometry':{'obstacle_price':104.0,'obstacle_distance_pct':4.0,'continuation_strong':False,'breakout':{'confirmed':False}}}
    d.update(kw); return d


def test_actionable_now_has_complete_plan():
    x=p.build(base())
    assert x['status']=='ACTIONABLE' and x['entry_mode']=='NOW'
    assert x['stop_loss']<x['entry']<x['tp1']<x['tp2']
    assert x['rr_tp1']>=1 and x['rr_tp2']>=2


def test_blocked_near_resistance_becomes_breakout_plan():
    d=base(execution_ready=False,production_signal_qualified=False,structural_geometry={'obstacle_price':101.0,'obstacle_distance_pct':1.0,'continuation_strong':True,'breakout':{'confirmed':False}})
    x=p.build(d)
    assert x['status']=='CONDITIONAL' and x['entry_mode']=='BREAKOUT'
    assert x['entry']>101.0 and x['stop_loss']<x['entry']<x['tp1']<x['tp2']


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
