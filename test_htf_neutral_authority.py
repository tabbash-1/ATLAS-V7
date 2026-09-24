from htf_structural_thesis import analyze_frames
from unittest.mock import patch

def state(bias):
    return {"ok": True, "bias": bias, "confidence": "TREND_ONLY", "price": 100.0, "impulse": "NEUTRAL", "volume_state": "NORMAL", "last_swing_high": 105.0, "last_swing_low": 95.0, "momentum_slope": "FLAT", "price_location": "MID_RANGE", "current_phase": "CONSOLIDATION_OR_TRANSITION", "candle": {}, "structure_event": "NONE"}

def run(b4, b12, proposed):
    seq={"1h":state(proposed),"4h":state(b4),"12h":state(b12),"1d":state("NEUTRAL")}
    with patch("htf_structural_thesis.analyze_frame", side_effect=lambda rows,tf: seq[tf]):
        return analyze_frames({tf:[{}]*60 for tf in seq}, proposed)

def test_neutral_authority_fails_closed():
    for b4,b12,proposed in [("SHORT","NEUTRAL","SHORT"),("NEUTRAL","LONG","LONG")]:
        x=run(b4,b12,proposed)
        assert x["status"]=="WAIT"
        assert x["product_direction"] is None
        assert x["direction"] is None
        assert x["reason"]=="4H_12H_NOT_ALIGNED"

def test_true_opposition_fails_closed():
    x=run("LONG","SHORT","LONG")
    assert x["status"]=="WAIT"
    assert x["product_direction"] is None
    assert x["reason"]=="4H_12H_NOT_ALIGNED"
