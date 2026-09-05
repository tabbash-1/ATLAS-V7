import atlas_product_readiness_gate as g

# This suite is intentionally dependency-free so the forward evidence workflow
# can enforce readiness invariants without installing pytest.


def base():
    p={
      'canonical_contract':'analyst_output','product_horizon':'4-12H','live_execution':False,'can_override_production':False,
      'portfolio':{'avg_r':0.4,'net_r':12.0},'trades':[]
    }
    i={'append_only_verified':True}
    a={'analysis_only':True,'live_execution':False,'can_override_production':False,'can_change_score':False,'can_change_threshold':False,'counts':{'context_complete':0}}
    return p,i,a


def test_gate_fails_closed_while_forward_sample_is_immature():
    p,i,a=base()
    out=g.build(p,i,a)
    assert out['technical_ready'] is True
    assert out['forward_evidence_ready'] is False
    assert out['state']=='TECHNICALLY_READY_EVIDENCE_PENDING'
    assert out['claim_policy']['may_claim_forward_edge_validated'] is False
    assert out['claim_policy']['may_claim_profitable'] is False
    assert out['analysis_only'] is True and out['live_execution'] is False


def test_gate_passes_only_after_preregistered_forward_requirements():
    p,i,a=base()
    p['trades']=[{'direction':'LONG','settlement':{'terminal':True}} for _ in range(15)] + [{'direction':'SHORT','settlement':{'terminal':True}} for _ in range(15)]
    out=g.build(p,i,a)
    assert out['forward_evidence_ready'] is True
    assert out['state']=='FORWARD_EVIDENCE_GATE_PASSED'
    assert out['claim_policy']['may_claim_forward_edge_validated'] is True
    assert out['claim_policy']['may_claim_profitable'] is False


def test_any_technical_contract_break_blocks_readiness():
    p,i,a=base(); p['live_execution']=True
    out=g.build(p,i,a)
    assert out['technical_ready'] is False
    assert out['state']=='BLOCKED_TECHNICAL'
