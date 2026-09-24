from atlas_trader_brain import assess

def base(alignment):
    return {
        "product_direction":"SHORT","entry_confirmation_direction":"SHORT",
        "direction_alignment":alignment,"htf_core_geometry":{"ready":True},
        "trade_plan":{"rr_tp2":2.1,"core_plan":{"entry_mode":"NOW"}},
    }

def test_explicit_htf_conflict_remains_fatal():
    out=assess(base("CONFLICT"))
    assert "TRADER_HTF_CONFLICT" in out["fatal_blockers"]
    assert out["stage"]=="NO_TRADE"

def test_unknown_or_lagging_alignment_waits_not_false_conflict():
    out=assess(base("NEUTRAL"))
    assert "TRADER_HTF_CONFLICT" not in out["fatal_blockers"]
    assert "TRADER_WAIT_HTF_ALIGNMENT_EVIDENCE" in out["fatal_blockers"]
    assert out["stage"]!="TRADE_READY"

def test_accepted_alignment_can_reach_trade_ready():
    out=assess(base("CONDITIONAL_ALIGNED_12H_NEUTRAL"))
    assert out["stage"]=="TRADE_READY"
