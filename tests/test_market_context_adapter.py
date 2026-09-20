from market_context_adapter import from_4h_klines

def candles(n=200,start=100,step=1):
    return [{"close":start+i*step} for i in range(n)]

def test_adapter_detects_extended_market_from_real_candle_shape():
    x=from_4h_klines(candles(),trend_direction="LONG",htf_alignment="ALIGNED",event_risk="LOW")
    assert x["context_source"]=="ATLAS_4H_KLINES"
    assert x["context"]["return_7d_pct"] is not None
    assert x["decision"]=="WAIT"
    assert x["reason"]=="AVOID_CHASING_EXTENDED_MOVE"
    assert x["can_override_canonical_decision"] is False

def test_adapter_preserves_htf_conflict():
    x=from_4h_klines(candles(step=.05),trend_direction="LONG",htf_alignment="CONFLICT",event_risk="LOW")
    assert x["decision"]=="WAIT" and x["reason"]=="HTF_CONFLICT"
