from breadth_reversal_caution_research import assess

def test_historical_reversal_shape_is_caution_not_short():
    x=assess(previous_bullish_ratio=.857,bullish_ratio=.286,lost_bullish_ratio=.571,btc_rsi_delta=-4.17)
    assert x["state"]=="REVERSAL_CAUTION"
    assert x["can_emit_short"] is False and x["can_force_exit"] is False
    assert x["can_override_production"] is False

def test_small_breadth_loss_fails_closed():
    x=assess(previous_bullish_ratio=.70,bullish_ratio=.65,lost_bullish_ratio=.05,btc_rsi_delta=-2)
    assert not x["eligible"]
