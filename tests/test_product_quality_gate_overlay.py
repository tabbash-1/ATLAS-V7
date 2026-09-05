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
    assert r['analysis_only'] is True and r['live_execution'] is False


def test_non_quarantined_setup_passes_unchanged():
    a=atlas_with(base_row(playbook='BREAKOUT_CONFIRMED_LONG'))
    qg.install(a)
    r=a.production_decision('BTCUSDT')
    assert r['setup_quality_gate']['status']=='PASS'
    assert r['actionable_decision']=='LONG'
    assert r['primary_analysis']['decision']=='LONG'


def test_short_is_not_blanket_blocked():
    a=atlas_with(base_row(candidate_direction='SHORT',regime='TREND_DOWN',playbook='MARKET_CONTINUATION_SHORT',actionable_decision='SHORT'))
    qg.install(a)
    r=a.production_decision('BTCUSDT')
    assert r['setup_quality_gate']['status']=='PASS'
    assert r['actionable_decision']=='SHORT'
