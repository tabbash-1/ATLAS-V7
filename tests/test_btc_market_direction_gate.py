import btc_market_direction_gate as g


def ev(regime, confidence=81):
    return {"btc": {"regime": regime, "confidence": confidence}}


def test_bearish_btc_blocks_alt_long():
    x=g.assess("ADAUSDT","LONG",ev("BREAKDOWN_DOWN"))
    assert x["pass"] is False and x["reason"]=="BTC_REGIME_OPPOSES_ALT_DIRECTION"


def test_bullish_btc_blocks_alt_short():
    assert g.assess("BNBUSDT","SHORT",ev("TREND_UP"))["pass"] is False


def test_aligned_direction_passes():
    assert g.assess("ADAUSDT","SHORT",ev("TREND_DOWN"))["pass"] is True
    assert g.assess("BNBUSDT","LONG",ev("BREAKOUT_UP"))["pass"] is True


def test_unknown_or_low_confidence_fails_safe():
    assert g.assess("ADAUSDT","LONG",ev("UNKNOWN"))["pass"] is False
    assert g.assess("ADAUSDT","LONG",ev("TREND_UP",50))["pass"] is False


def test_btc_itself_is_not_recursively_blocked():
    assert g.assess("BTCUSDT","SHORT",ev("TREND_UP"))["pass"] is True
