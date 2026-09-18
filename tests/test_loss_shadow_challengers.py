import loss_shadow_challengers as m

def test_contract_is_research_only():
 p=m.validate(); s=p["safety"]
 assert s["production_impact"]=="NONE"
 assert s["production_threshold"]==68
 assert p["product_horizon"]=="4-12H"

def test_three_distinct_failure_hypotheses():
 assert set(m.CHALLENGERS)=={"ENTRY_CONFIRMATION_DELAY","EARLY_THESIS_FAILURE","PROFIT_PROTECTION_TIME_DECAY"}

def test_no_automatic_promotion():
 p=m.contract()
 assert p["promotion"]["automatic"] is False
 assert p["promotion"]["requires_prospective_paired_evidence"] is True
 assert p["promotion"]["minimum_paired_sample"]>=30
