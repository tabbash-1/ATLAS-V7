from market_breadth_exhaustion_research import assess

def test_historical_exhaustion_shape_only_marks_caution():
    x=assess(bullish_ratio=6/7,btc_trend="BULLISH",btc_rsi14=79.03,btc_momentum_24h_pct=2.589)
    assert x["state"]=="LONG_EXHAUSTION_CAUTION"
    assert x["can_emit_short"] is False and x["can_force_exit"] is False
    assert x["can_override_production"] is False

def test_early_long_shape_not_exhausted():
    x=assess(bullish_ratio=5/7,btc_trend="BULLISH",btc_rsi14=71.79,btc_momentum_24h_pct=.983)
    assert x["state"]=="NO_EXHAUSTION_EVIDENCE"

def test_missing_data_fails_closed():
    x=assess(bullish_ratio=.9,btc_trend="BULLISH",btc_rsi14=None,btc_momentum_24h_pct=3)
    assert not x["eligible"] and x["missing"]
