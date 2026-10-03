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
    v={'current_geometry':{'version':'ATLAS_GEOMETRY_V6_MIN_1_5_ATR_INVALIDATION','summary':{'terminal':30,'avg_r':0.4,'net_r':12.0,'by_direction':{'long':{'n':15,'avg_r':0.5,'net_r':7.5},'short':{'n':15,'avg_r':0.3,'net_r':4.5}}},'cost_adjusted':{'terminal_costed':30,'avg_net_r':0.2,'net_r':6.0,'profit_factor_r':1.4}}}
    out=g.build(o,i,validation=v)
    assert out['forward_evidence_ready'] is True and out['state']=='FORWARD_EVIDENCE_GATE_PASSED'
    assert out['claim_policy']['may_claim_profitable'] is False

def test_non_final_gate_authority_blocks_readiness():
    o,i=base(); o['decision_source_of_truth']='analyst_output'
    out=g.build(o,i)
    assert out['technical_ready'] is False and out['state']=='BLOCKED_TECHNICAL'


def test_positive_gross_edge_cannot_pass_when_cost_adjusted_edge_is_negative():
    o,i=base()
    o['signals']['rows']=[{'direction':'LONG','settlement':{'r_multiple':0.5}} for _ in range(15)]+[{'direction':'SHORT','settlement':{'r_multiple':0.3}} for _ in range(15)]
    v={'current_geometry':{'version':'ATLAS_GEOMETRY_V6_MIN_1_5_ATR_INVALIDATION','summary':{'terminal':30,'avg_r':0.4,'net_r':12.0,'by_direction':{'long':{'n':15,'avg_r':0.5,'net_r':7.5},'short':{'n':15,'avg_r':0.3,'net_r':4.5}}},'cost_adjusted':{'terminal_costed':30,'avg_net_r':-0.02,'net_r':-0.6,'profit_factor_r':0.94}}}
    out=g.build(o,i,validation=v)
    assert out['forward_evidence_ready'] is False
    names={x['name'] for x in out['blockers']}
    assert 'POSITIVE_COST_ADJUSTED_AVERAGE_R' in names
    assert 'POSITIVE_COST_ADJUSTED_NET_R' in names
    assert 'COST_ADJUSTED_PROFIT_FACTOR' in names


def test_short_lane_cannot_hide_behind_profitable_long_lane():
    o,i=base()
    o['signals']['rows']=[{'direction':'LONG','settlement':{'r_multiple':1.0}} for _ in range(25)]+[{'direction':'SHORT','settlement':{'r_multiple':-1.0}} for _ in range(5)]
    o['path_summary']={'avg_r':20/30,'net_r':20.0}
    v={'current_geometry':{'version':'ATLAS_GEOMETRY_V6_MIN_1_5_ATR_INVALIDATION','summary':{'terminal':30,'avg_r':20/30,'net_r':20.0,'by_direction':{'long':{'n':25,'avg_r':1.0,'net_r':25.0},'short':{'n':5,'avg_r':-1.0,'net_r':-5.0}}},'cost_adjusted':{'terminal_costed':30,'avg_net_r':0.3,'net_r':9.0,'profit_factor_r':1.5}}}
    out=g.build(o,i,validation=v)
    assert out['forward_evidence_ready'] is False
    names={x['name'] for x in out['blockers']}
    assert 'POSITIVE_SHORT_FORWARD_AVERAGE_R' in names
    assert 'POSITIVE_SHORT_FORWARD_NET_R' in names


def test_quick_trade_zero_signals_is_explicitly_no_evidence():
    o,i=base()
    q={'summary':{'total_signals':0,'closed_or_expired':0}}
    out=g.build(o,i,quick=q)
    assert out['quick_trade_evidence']['status']=='NO_EVIDENCE'
    assert out['quick_trade_evidence']['can_support_readiness'] is False


def test_legacy_post_v2_evidence_cannot_satisfy_current_v6_readiness():
    o,i=base()
    o['signals']['rows']=[{'direction':'LONG','settlement':{'r_multiple':1.0}} for _ in range(15)]+[{'direction':'SHORT','settlement':{'r_multiple':1.0}} for _ in range(15)]
    v={'post_v2_cost_adjusted':{'terminal_costed':30,'avg_net_r':0.8,'net_r':24.0,'profit_factor_r':4.0}}
    out=g.build(o,i,validation=v)
    assert out['forward_evidence_ready'] is False
    assert out['historical_post_v2_excluded_from_current_readiness'] is True
    assert any(x['name']=='CURRENT_GEOMETRY_V6_EVIDENCE' and not x['passed'] for x in out['blockers'])
