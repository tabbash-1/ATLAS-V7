import ai_trade_council as council


def xrp_like_decision():
    return {
        'symbol':'XRPUSDT','entry':1.5301,'candidate_direction':'LONG','decision':'WAIT','signal_qualified':False,
        'score':64,'direction_votes_long':4,'direction_votes_short':0,'relative_strength_score':45.65,
        'tactical_opportunity':{'direction':'LONG','target':1.544125,'stop_loss':1.51346,'risk_reward':0.843,'usable_room_pct':0.917},
        'indicators':{'atr14':0.0256,'rsi14':65.27,'momentum_24h_pct':4.43,'volume_ratio':0.191,'ema20':1.4968,'ema50':1.4841},
        'score_attribution':{'trend_base':68,'obstacle_adjustment':-4,'obstacle_distance_pct':1.078},
        'structural_geometry':{
            'source':'PRIOR_SWING_HIGH','obstacle_price':1.5466,
            'breakout':{'prior_24h_high':1.5505,'prior_24h_low':1.4532,'confirmed':False}
        }
    }


def test_long_breakout_entry_is_above_all_resistance():
    d=xrp_like_decision()
    rows=council._counterfactuals(d,'LONG',65)
    brk=next(x for x in rows if x['scenario']=='WAIT_BREAKOUT')
    assert brk['structure_anchored'] is True
    assert brk['reference_level'] == 1.5505
    assert brk['entry'] > 1.5505
    assert brk['stop_loss'] < brk['entry'] < brk['target']
    assert '1H price closes/holds above' in brk['trigger']


def test_short_breakdown_entry_is_below_all_support():
    d=xrp_like_decision()
    d['entry']=1.50
    d['candidate_direction']='SHORT'
    d['structural_geometry']={'source':'PRIOR_SWING_LOW','obstacle_price':1.47,'breakout':{'prior_24h_low':1.46,'prior_24h_high':1.56}}
    rows=council._counterfactuals(d,'SHORT',65)
    brk=next(x for x in rows if x['scenario']=='WAIT_BREAKOUT')
    assert brk['reference_level'] == 1.46
    assert brk['entry'] < 1.46
    assert brk['target'] < brk['entry'] < brk['stop_loss']


def test_no_structure_means_no_fake_breakout_scenario():
    d=xrp_like_decision()
    d['structural_geometry']={'source':'NO_PRIOR_RESISTANCE_AHEAD','obstacle_price':None,'breakout':{'prior_24h_high':1.50}}
    rows=council._counterfactuals(d,'LONG',65)
    assert not any(x['scenario']=='WAIT_BREAKOUT' for x in rows)


if __name__ == '__main__':
    test_long_breakout_entry_is_above_all_resistance()
    test_short_breakdown_entry_is_below_all_support()
    test_no_structure_means_no_fake_breakout_scenario()
    print('AI breakout structure tests: ok')
