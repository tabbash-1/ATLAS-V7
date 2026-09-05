import types
import product_quality_gate_overlay as qg


def atlas_with(row):
    a=types.SimpleNamespace()
    a.production_decision=lambda symbol: dict(row)
    return a


def base_row(**extra):
    row={
        'ok':True,'symbol':'BTCUSDT','candidate_direction':'LONG',
        'production_signal_qualified':True,'score':75.0,'signal_threshold':68.0,
        'regime':'TREND_UP','playbook':'TREND_PULLBACK_LONG',
        'actionable_decision':'LONG','actionable_reason':'EXECUTION_READY',
        'execution_ready':True,'analysis_only':True,'live_execution':False,
        'entry':100.0,'stop_loss':98.0,'take_profit':104.0,'risk_reward':2.0,
        'geometry_gate':{'qualified':True},
        'trade_plan':{'entry':100.0,'stop_loss':98.0,'tp1':102.0,'tp2':104.0,'rr_tp2':2.0,'entry_trigger':'Verified setup remains valid.','invalidation':'4H structure fails.'},
        'primary_analysis':{'lane':'CORE_4_12H','horizon':'4-12H','decision':'LONG','analysis_ready':True,'live_execution':False},
        'timeframe_matrix':{'core_4_12h':{'lane':'CORE_4_12H','decision':'LONG'}},
        'best_available_action':{'action':'LONG','status':'ACTIONABLE','opportunity_state':'ACTIONABLE','can_execute':False},
    }
    row.update(extra); return row


def test_quarantined_setup_demotes_only_product_action():
    a=atlas_with(base_row())
    qg.install(a)
    r=a.production_decision('BTCUSDT')
    assert r['setup_quality_gate']['status']=='BLOCK'
    assert r['production_signal_qualified'] is True
    assert r['score']==75.0 and r['signal_threshold']==68.0
    assert r['production_threshold_changed_by_quality_gate'] is False
    assert r['actionable_decision']=='WAIT'
    assert r['primary_analysis']['decision']=='WAIT'
    assert r['primary_analysis']['analysis_ready'] is False
    assert r['best_available_action']['action']=='WAIT'
    assert r['analyst_output']['decision']=='WAIT'
    assert r['analyst_output']['entry'] is None
    assert r['analyst_output']['candidate_plan']['entry']==100.0
    assert r['analyst_output']['horizon']=='4-12H'
    assert r['analyst_output']['confidence_basis']=='PRODUCTION_SCORE_NOT_PROBABILITY'
    assert r['canonical_product_contract']=='analyst_output'
    assert r['analysis_only'] is True and r['live_execution'] is False


def test_non_quarantined_setup_passes_with_complete_analyst_output():
    a=atlas_with(base_row(playbook='BREAKOUT_CONFIRMED_LONG'))
    qg.install(a)
    r=a.production_decision('BTCUSDT')
    out=r['analyst_output']
    assert r['setup_quality_gate']['status']=='PASS'
    assert r['actionable_decision']=='LONG'
    assert r['primary_analysis']['decision']=='LONG'
    assert out['decision']=='LONG'
    assert out['entry']==100.0 and out['stop_loss']==98.0 and out['take_profit']==104.0
    assert out['risk_reward']==2.0
    assert out['invalidation']=='4H structure fails.'
    assert out['analysis_only'] is True and out['live_execution'] is False


def test_short_is_not_blanket_blocked():
    a=atlas_with(base_row(candidate_direction='SHORT',regime='TREND_DOWN',playbook='MARKET_CONTINUATION_SHORT',actionable_decision='SHORT'))
    qg.install(a)
    r=a.production_decision('BTCUSDT')
    assert r['setup_quality_gate']['status']=='PASS'
    assert r['actionable_decision']=='SHORT'
    assert r['analyst_output']['decision']=='SHORT'
