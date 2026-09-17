import atlas_final_production_v2_settlement as f

def base(decision='NO_PROMOTION',passing=None): return {'schema':'ATLAS_PROMOTION_GATE_V1','promotion_decision':decision,'passing_cohorts':passing or []}
def test_no_promotion_preserves_current_production():
    r=f.settle(base()); assert r['final_release_action']=='PRESERVE_CURRENT_PRODUCTION'; assert r['production_changed'] is False
def test_threshold_never_changes():
    r=f.settle(base()); assert r['threshold_before']==68 and r['threshold_after']==68
def test_no_semantic_mutation_flags():
    r=f.settle(base()); assert not r['score_logic_changed'] and not r['risk_logic_changed'] and not r['sl_tp_logic_changed'] and not r['final_trade_gate_changed']
def test_eligible_evidence_still_does_not_auto_promote():
    r=f.settle(base('ELIGIBLE_FOR_MANUAL_PRODUCTION_REVIEW',['SYNTHETIC'])); assert r['final_release_action']=='MANUAL_IMPLEMENTATION_REVIEW_REQUIRED'; assert r['production_changed'] is False; assert r['automatic_promotion'] is False
def test_preservation_does_not_create_fake_new_epoch():
    assert f.settle(base())['new_performance_epoch_required'] is False
def test_future_semantic_change_requires_new_epoch():
    assert f.settle(base('ELIGIBLE_FOR_MANUAL_PRODUCTION_REVIEW',['X']))['new_performance_epoch_required'] is True
