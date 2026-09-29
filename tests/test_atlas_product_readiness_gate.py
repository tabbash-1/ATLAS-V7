import atlas_product_readiness_gate as g

def base():
    rows=[]
    o={'decision_source_of_truth':'FINAL_TRADE_GATE','product_horizon':'4-12H','legacy_backfill_allowed':False,'legacy_score_path_research_included':False,'safety':{'live_execution':False,'can_override_production':False},'signals':{'rows':rows},'path_summary':{'avg_r':0.4,'net_r':12.0},'official_trade_authority':'PAPER_PORTFOLIO_CANONICAL_FINAL_GATE_EXECUTION_ELIGIBLE_ENTRIES'}
    i={'append_only_verified':True}
    return o,i

def test_gate_fails_closed_while_forward_sample_is_immature():
    o,i=base(); out=g.build(o,i)
    assert out['technical_ready'] is True and out['forward_evidence_ready'] is False
    assert out['state']=='TECHNICALLY_READY_EVIDENCE_PENDING'
    assert out['canonical_contract']=='FINAL_TRADE_GATE'
    assert out['research_lane_excluded_from_readiness']=='analyst_output'

def test_gate_passes_only_after_preregistered_forward_requirements():
    o,i=base()
    o['signals']['rows']=[{'direction':'LONG','settlement':{'r_multiple':0.5}} for _ in range(15)]+[{'direction':'SHORT','settlement':{'r_multiple':0.3}} for _ in range(15)]
    out=g.build(o,i)
    assert out['forward_evidence_ready'] is True and out['state']=='FORWARD_EVIDENCE_GATE_PASSED'
    assert out['claim_policy']['may_claim_profitable'] is False

def test_non_final_gate_authority_blocks_readiness():
    o,i=base(); o['decision_source_of_truth']='analyst_output'
    out=g.build(o,i)
    assert out['technical_ready'] is False and out['state']=='BLOCKED_TECHNICAL'
