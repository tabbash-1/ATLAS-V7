import profitability_forward_promotion as m

def test_gate_fails_closed_without_forward_proof():
    x=m.evaluate({"overall":{"n":29,"avg_r":.5,"profit_factor_r":2},"max_drawdown_r":2},{"opportunity_capture_rate":.8})
    assert x["state"]=="FORWARD_SHADOW_COLLECTING"
    assert x["promotion"]["automatic"] is False
    assert x["safety"]["production_threshold"]==68

def test_gate_can_become_eligible_but_never_auto_promotes():
    x=m.evaluate({"overall":{"n":30,"avg_r":.2,"profit_factor_r":1.4},"max_drawdown_r":3},{"opportunity_capture_rate":.6})
    assert x["state"]=="PROMOTION_ELIGIBLE"
    assert all(x["checks"].values())
    assert x["promotion"]["requires_new_reviewed_pr"]
    assert not x["promotion"]["production_change_allowed_by_this_module"]
