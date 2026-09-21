from regime_transition_challenger import assess

def row(rr=2.2, reason="HTF_CONFLICT"):
    return {"candidate_direction":"LONG","canonical_product_decision":"WAIT","wait_reason":reason,
      "htf_core_geometry":{"ready":True},"analyst_output":{"risk_reward":rr},
      "htf_thesis":{"frames":{"1h":{"bias":"LONG"},"4h":{"bias":"LONG"},"12h":{"bias":"NEUTRAL"},"1d":{"bias":"NEUTRAL"}}}}

def test_aligned_transition_is_shadow_long():
    x=assess(row(),{"regime":"TREND_UP"},{"regime":"BREAKOUT_UP"},{"direction":"LONG","aligned_ratio":.71},{"direction":"LONG","crowded":False})
    assert x["eligible"] and x["decision"]=="LONG"
    assert x["can_override_production"] is False

def test_btc_opposition_blocks():
    x=assess(row(),{"regime":"TREND_UP"},{"regime":"TREND_DOWN"},{"direction":"LONG","aligned_ratio":.8},{"direction":"LONG"})
    assert not x["eligible"] and "BTC_REGIME_NOT_ALIGNED" in x["blockers"]

def test_missing_breadth_fails_closed():
    x=assess(row(),{"regime":"TREND_UP"},{"regime":"TREND_UP"},None,{"direction":"LONG"})
    assert not x["eligible"] and "BREADTH_MISSING" in x["blockers"]

def test_crowded_derivatives_blocks():
    x=assess(row(),{"regime":"TREND_UP"},{"regime":"TREND_UP"},{"direction":"LONG","aligned_ratio":.7},{"direction":"LONG","crowded":True})
    assert not x["eligible"] and "DERIVATIVES_CROWDED" in x["blockers"]

def test_rr_below_two_blocks():
    x=assess(row(1.8),{"regime":"TREND_UP"},{"regime":"TREND_UP"},{"direction":"LONG","aligned_ratio":.7},{"direction":"LONG"})
    assert not x["eligible"] and "NET_RR_BELOW_2_OR_MISSING" in x["blockers"]

def test_non_htf_wait_cannot_be_reclassified():
    x=assess(row(reason="EVENT_RISK"),{"regime":"TREND_UP"},{"regime":"TREND_UP"},{"direction":"LONG","aligned_ratio":.7},{"direction":"LONG"})
    assert not x["eligible"] and "NOT_HTF_CONFLICT_WAIT" in x["blockers"]
