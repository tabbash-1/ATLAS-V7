from supabase_early_transition_prospective import capture,promotion_eligible

def test_capture_keeps_canonical_decision_immutable():
    p={"captured_at":"2026-10-02T10:00:00Z","symbol":"BTCUSDT",
       "canonical_decision_id":"d1","canonical_decision":"WAIT"}
    f={"regime":"NEUTRAL","btc_return_1h_pct":-0.5,"price_change_24h_pct":-1,
       "oi_change_pct":-1,"taker_imbalance":-0.2,"relative_volume":0.8}
    x=capture(p,f)
    assert x["canonical_decision"]=="WAIT"
    assert x["early_transition"]["direction"]=="SHORT"
    assert x["can_override_final_gate"] is False
    assert x["historical_cross_system_replay_valid"] is False

def test_v1_cannot_promote_even_with_records():
    assert promotion_eligible([{"direction":"SHORT"}]*1000) is False
