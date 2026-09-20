from market_context_reasoning import build, VERSION

def test_extended_bull_trend_waits_instead_of_chasing():
    x=build({"trend_direction":"LONG","return_7d_pct":31,"return_30d_pct":159,"rsi":75,"htf_alignment":"ALIGNED","event_risk":"LOW","catalyst_bias":"POSITIVE"})
    assert x["version"]==VERSION
    assert x["decision"]=="WAIT"
    assert x["reason"]=="AVOID_CHASING_EXTENDED_MOVE"
    assert x["overextended"] is True
    assert x["can_override_canonical_decision"] is False

def test_event_risk_blocks_otherwise_clean_long():
    x=build({"trend_direction":"LONG","return_7d_pct":5,"rsi":58,"htf_alignment":"ALIGNED","event_risk":"HIGH"})
    assert x["decision"]=="WAIT" and x["reason"]=="EVENT_RISK"

def test_clean_aligned_trend_is_shadow_long_only():
    x=build({"trend_direction":"LONG","return_7d_pct":5,"return_30d_pct":12,"rsi":58,"htf_alignment":"ALIGNED","event_risk":"LOW"})
    assert x["decision"]=="LONG"
    assert x["analysis_only"] is True and x["live_execution"] is False
    assert x["can_change_score"] is False and x["can_change_threshold"] is False

def test_htf_conflict_remains_wait():
    x=build({"trend_direction":"LONG","rsi":55,"htf_alignment":"CONFLICT","event_risk":"LOW"})
    assert x["decision"]=="WAIT" and x["reason"]=="HTF_CONFLICT"
