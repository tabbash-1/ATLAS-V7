import market_regime_engine as mre


def candles(start=100.0, step=0.2, n=120, wick=0.15):
    out = []
    px = start
    for i in range(n):
        op = px
        close = px + step
        high = max(op, close) + wick
        low = min(op, close) - wick
        out.append({'open': op, 'high': high, 'low': low, 'close': close, 'volume': 10.0})
        px = close
    return out


def choppy(n=120):
    out = []
    for i in range(n):
        op = 100.0 + (0.10 if i % 2 else -0.10)
        close = 100.0 + (-0.10 if i % 2 else 0.10)
        out.append({'open': op, 'high': 100.18, 'low': 99.82, 'close': close, 'volume': 10.0})
    return out


def test_clean_uptrend_is_independently_bullish():
    out = mre.classify(candles(step=0.25))
    assert out['regime'] in ('TREND_UP', 'BREAKOUT_UP', 'VOLATILITY_EXPANSION_UP')
    assert out['efficiency_ratio_24h'] > 0.32


def test_clean_downtrend_is_independently_bearish():
    out = mre.classify(candles(start=150.0, step=-0.25))
    assert out['regime'] in ('TREND_DOWN', 'BREAKDOWN_DOWN', 'VOLATILITY_EXPANSION_DOWN')
    assert out['efficiency_ratio_24h'] > 0.32


def test_chop_is_not_labeled_directional_trend():
    out = mre.classify(choppy())
    assert out['regime'] in ('RANGE', 'COMPRESSION', 'TRANSITION')
    assert out['regime'] not in ('TREND_UP', 'TREND_DOWN')


def test_analyze_keeps_btc_context_separate():
    out = mre.analyze('SOLUSDT', candles(start=50, step=0.1), candles(start=100, step=-0.2))
    assert out['asset_regime'] in ('TREND_UP', 'BREAKOUT_UP', 'VOLATILITY_EXPANSION_UP')
    assert out['btc_regime'] in ('TREND_DOWN', 'BREAKDOWN_DOWN', 'VOLATILITY_EXPANSION_DOWN')
    assert out['independent_of_signal_direction'] is True
    assert out['can_override_production'] is False
