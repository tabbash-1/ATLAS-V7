import ai_trade_council as a


def prod_ready():
    return {
      'ok':True,'symbol':'BTCUSDT','generated_at':'now','entry':80477.4,
      'candidate_direction':'LONG','decision':'LONG','score':78,'signal_threshold':68,
      'signal_qualified':True,'production_signal_qualified':True,'execution_ready':True,'actionable_decision':'LONG',
      'direction_votes_long':4,'direction_votes_short':0,'relative_volume':0.93,
      'relative_strength_score':50,'futures_score':0,
      'indicators':{'ema20':79000,'ema50':78000,'rsi14':70,'momentum_24h_pct':5,'atr14':700},
      'tactical_opportunity':{'status':'LONG_TACTICAL','direction':'LONG','risk_reward':1.43,'target':81500,'stop_loss':79750},
      'trade_plan':{'status':'ACTIONABLE','action':'BUY','direction':'LONG','entry_mode':'NOW','entry':80477.4,'stop_loss':79604.41,'tp1':81350.0,'tp2':82291.1,'rr_tp1':1.0,'rr_tp2':2.08,'entry_trigger':'Verified Production setup is executable now.'},
      'score_attribution':{'trend_base':68,'momentum_adjustment':6,'market_breadth_adjustment':3,'obstacle_adjustment':0}
    }


def test_actionable_scenario_is_production_now():
    x=a.analyze(prod_ready())
    assert x['best_counterfactual']['scenario']=='PRODUCTION_NOW'


def test_actionable_levels_match_canonical_plan():
    b=a.analyze(prod_ready())['best_counterfactual']
    assert b['entry']==80477.4 and b['stop_loss']==79604.41 and b['target']==82291.1


def test_actionable_hybrid_confirms():
    x=a.analyze(prod_ready())
    assert x['hybrid_judge']['decision']=='CONFIRM'


def test_actionable_canonical_action_is_buy():
    x=a.analyze(prod_ready())
    assert x['canonical_action']['action']=='BUY'


def test_ai_never_says_wait_when_production_is_actionable():
    x=a.analyze(prod_ready())
    assert x['production_qualified'] is True
    assert x['canonical_action']['status']=='ACTIONABLE'
    assert x['best_counterfactual']['scenario']=='PRODUCTION_NOW'


def test_non_actionable_can_still_use_counterfactuals():
    d=prod_ready(); d['execution_ready']=False; d['actionable_decision']='WAIT'; d['production_signal_qualified']=False; d['signal_qualified']=False
    d['trade_plan']={'status':'CONDITIONAL','action':'BUY_ONLY_IF','direction':'LONG','entry_mode':'BREAKOUT','entry':81345.0,'stop_loss':80799.0,'tp1':81891.0,'tp2':82509.0,'rr_tp1':1.0,'rr_tp2':2.13,'entry_trigger':'Buy only after 1H close/hold above resistance.'}
    x=a.analyze(d)
    assert x['canonical_action']['status']=='CONDITIONAL'
    assert x['canonical_action']['action']=='BUY_ONLY_IF'
