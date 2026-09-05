import analyst_forward_attribution as a


def test_compact_context_and_tags():
    d={
      'symbol':'BNBUSDT','candidate_direction':'LONG','score':82,'signal_threshold':68,
      'playbook':'BREAKOUT_CONFIRMED_LONG','regime':'BREAKOUT_UP','production_signal_qualified':True,
      'direction_votes':4,'relative_strength_score':55,'futures_available':True,'futures_score':-20,
      'volume_quality':100,'relative_volume':4,
      'score_attribution':{'trend_base':68,'volume_bonus':10,'futures_adjustment':-2,'futures_reason':'OPPOSED','extension_guard_reason':'RSI_SANE'},
      'indicators':{'rsi14':78,'atr14':3,'momentum_24h_pct':2},
      'structural_geometry':{'source':'ATR','breakout':{'confirmed':True,'beyond_prior_24h_range':True,'current_body_atr':1.5,'paced_relative_volume':4}},
      'analyst_output':{'decision':'LONG','confidence':82,'signal_threshold':68,'playbook':'BREAKOUT_CONFIRMED_LONG','regime':'BREAKOUT_UP','production_qualified_raw':True,'geometry_ready_raw':True,'analysis_only':True,'live_execution':False,'setup_quality_gate':{'status':'PASS','reason':'SETUP_NOT_IN_EVIDENCE_QUARANTINE'}}
    }
    c=a.compact_context(d)
    assert c['score']==82 and c['playbook']=='BREAKOUT_CONFIRMED_LONG'
    tags=a.evidence_tags(c)
    assert 'DERIVATIVES_OPPOSED' in tags
    assert 'LONG_RSI_EXTENDED' in tags


def test_failure_label_is_hypothesis_not_production_change():
    ctx={'decision':'SHORT','score':69,'threshold':68,'rsi14':45,'relative_volume':1.2,'futures_reason':'ALIGNED','futures_adjustment':1,'playbook':'TREND_SHORT','data_degraded':False}
    assert a.failure_hypothesis(ctx,{'status':'LOSS','terminal':True,'r_multiple':-1})=='MARGINAL_QUALIFICATION_RISK'
    out=a.build()
    assert out['canonical_contract']=='analyst_output'
    assert out['product_horizon']=='4-12H'
    assert out['analysis_only'] is True
    assert out['live_execution'] is False
    assert out['can_override_production'] is False
    assert out['can_change_score'] is False
    assert out['can_change_threshold'] is False
