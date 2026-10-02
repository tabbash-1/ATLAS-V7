from supabase_early_transition_research import assess

def test_validated_short_candidate_is_research_only():
    x=assess({"regime":"NEUTRAL","btc_return_1h_pct":-0.4,"price_change_24h_pct":-1,
              "oi_change_pct":-1,"taker_imbalance":-0.1,"relative_volume":0.8})
    assert x["eligible"] and x["direction"]=="SHORT"
    assert x["research_only"] and x["paper_only"]
    assert x["can_override_production"] is False
    assert x["can_override_final_gate"] is False
    assert x["live_execution"] is False

def test_long_fails_closed_even_with_positive_inputs():
    x=assess({"regime":"NEUTRAL","btc_return_1h_pct":0.5,"price_change_24h_pct":2,
              "oi_change_pct":2,"taker_imbalance":0.2,"relative_volume":1.5})
    assert not x["eligible"] and x["direction"]=="WAIT"

def test_missing_point_in_time_feature_fails_closed():
    x=assess({"regime":"NEUTRAL","btc_return_1h_pct":-0.5,"price_change_24h_pct":-2})
    assert not x["eligible"] and x["direction"]=="WAIT"
    assert any(b.startswith("MISSING_") for b in x["blockers"])

def test_wrong_regime_does_not_emit_short():
    x=assess({"regime":"UPTREND_CONTINUATION","btc_return_1h_pct":-0.5,"price_change_24h_pct":-2,
              "oi_change_pct":-1,"taker_imbalance":-0.2,"relative_volume":0.7})
    assert not x["eligible"] and x["direction"]=="WAIT"
