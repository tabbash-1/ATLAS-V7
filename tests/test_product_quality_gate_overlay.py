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
        'geometry_gate':{'status':'PASS','qualified':True,'reason':'RR_ONE_TO_ONE_OR_BETTER','primary_blocker':None,'blocker_codes':[],'checks':{'rr_meets_minimum':True},'reason_schema_version':'ATLAS_GEOMETRY_REASON_CODES_V1','version':'ATLAS_CANONICAL_GEOMETRY_TRUTH_V1'},
        'score_attribution':{'obstacle_reason':'ACCEPTABLE_PRIOR_STRUCTURE','futures_reason':'ALIGNED','obstacle_distance_pct':2.0},
        'futures_available':True,'relative_volume':1.3,'indicators':{'rsi14':61.0},
        'trade_plan':{'entry':100.0,'stop_loss':98.0,'tp1':102.0,'tp2':104.0,'rr_tp2':2.0,'entry_trigger':'Verified setup remains valid.','invalidation':'4H structure fails.','geometry_provenance':{'geometry_version':'G','entry_basis':'E','stop_basis':'S','tp1_basis':'T1','tp2_basis':'T2'}},
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
    assert r['analyst_output']['evidence_profile']['quality']=='BLOCKED'
    assert r['analyst_output']['geometry_readiness']['ready'] is True
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
    assert out['analysis_profile_version']==qg.PROFILE_VERSION
    assert out['evidence_profile']['threshold_changed'] is False
    assert 'GEOMETRY_PROVENANCE_COMPLETE' in out['evidence_profile']['confirmations']
    assert out['geometry_readiness']['reason_schema_version']=='ATLAS_GEOMETRY_REASON_CODES_V1'
    assert out['analysis_only'] is True and out['live_execution'] is False


def test_geometry_blockers_remain_visible_even_with_quality_gate_block():
    blocked_geometry={
        'status':'BLOCK','qualified':False,'reason':'GEOMETRY_INCOMPLETE',
        'primary_blocker':'MISSING_STOP','blocker_codes':['MISSING_STOP'],
        'checks':{'entry_present':True,'stop_present':False,'target_present':True},
        'reason_schema_version':'ATLAS_GEOMETRY_REASON_CODES_V1',
        'version':'ATLAS_CANONICAL_GEOMETRY_TRUTH_V1',
    }
    row=base_row(geometry_gate=blocked_geometry,actionable_decision='WAIT',actionable_reason='MISSING_STOP')
    a=atlas_with(row); qg.install(a)
    out=a.production_decision('BTCUSDT')['analyst_output']
    assert out['decision']=='WAIT'
    assert out['geometry_readiness']['primary_blocker']=='MISSING_STOP'
    assert out['geometry_readiness']['blocker_codes']==['MISSING_STOP']
    assert 'CLEAR_GEOMETRY_MISSING_STOP' in out['what_changes_status']


def test_shadow_structure_risk_is_warning_not_veto():
    row=base_row(playbook='BREAKOUT_CONFIRMED_LONG',score_attribution={'obstacle_reason':'CLOSE_PRIOR_STRUCTURE','obstacle_distance_pct':1.0,'futures_reason':'ALIGNED'})
    a=atlas_with(row); qg.install(a)
    r=a.production_decision('BTCUSDT')
    assert r['setup_quality_gate']['status']=='PASS'
    assert r['analyst_output']['decision']=='LONG'
    codes=[x['code'] for x in r['analyst_output']['evidence_profile']['warnings']]
    assert 'LONG_CLOSE_PRIOR_STRUCTURE_SHADOW_RISK' in codes
    assert r['score']==75.0 and r['signal_threshold']==68.0


def test_rejected_research_rules_never_auto_promote():
    a=atlas_with(base_row(playbook='BREAKOUT_CONFIRMED_LONG'))
    qg.install(a); r=a.production_decision('BTCUSDT')
    rejected=r['analyst_output']['evidence_profile']['research_rules_explicitly_not_promoted']
    assert 'LONG_ANTI_CHASE_VETO_REJECTED' in rejected
    assert 'VOLUME_ONLY_RANKING_OR_DEMOTION_REJECTED' in rejected
    assert 'NEUTRAL_RS_VETO_REJECTED' in rejected
    assert r['analyst_output']['evidence_profile']['only_quality_gate_can_change_canonical_decision'] is True


def test_short_is_not_blanket_blocked():
    a=atlas_with(base_row(candidate_direction='SHORT',regime='TREND_DOWN',playbook='MARKET_CONTINUATION_SHORT',actionable_decision='SHORT'))
    qg.install(a)
    r=a.production_decision('BTCUSDT')
    assert r['setup_quality_gate']['status']=='PASS'
    assert r['actionable_decision']=='SHORT'
    assert r['analyst_output']['decision']=='SHORT'
