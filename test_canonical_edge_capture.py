from offline_production_path_settlement import canonical_geometry
def decision(ready=True, canonical="LONG", plan="LONG", qualified=False):
    return {"signal_qualified":qualified,"canonical_decision":{"schema":"ATLAS_CANONICAL_DECISION_TRUTH_V1","canonical_source_present":True,"source_of_truth":"FINAL_TRADE_GATE","trade_ready":ready,"decision":canonical},"trade_plan":{"direction":plan,"entry":100,"stop_loss":95,"tp1":105,"tp2":110,"rr_tp1":1,"rr_tp2":2}}
def test_canonical_trade_ready_is_authority_not_legacy_score():
    assert canonical_geometry(decision(qualified=False)) is not None
def test_wait_never_enters_settlement_even_if_legacy_qualified():
    assert canonical_geometry(decision(ready=False,qualified=True)) is None
def test_direction_mismatch_fails_closed():
    assert canonical_geometry(decision(canonical="LONG",plan="SHORT")) is None
