"""ATLAS independent Market Regime Engine v1.

The Production scorer historically exposes a regime label derived from the same
signal direction. This module intentionally classifies regime independently from
any candidate trade using only price/volatility structure. It is shadow-only and
cannot change Production decisions.

Expected input: normalized hourly candles with open/high/low/close fields.
"""

from __future__ import annotations

VERSION = 'MARKET_REGIME_ENGINE_V1_INDEPENDENT'


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _ema(values, period):
    vals = [_f(x) for x in values]
    vals = [x for x in vals if x is not None]
    if len(vals) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    out = sum(vals[:period]) / period
    for x in vals[period:]:
        out = alpha * x + (1.0 - alpha) * out
    return out


def _true_ranges(ks):
    out = []
    prev_close = None
    for row in ks or []:
        high = _f(row.get('high')); low = _f(row.get('low')); close = _f(row.get('close'))
        if high is None or low is None or close is None:
            continue
        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        out.append(max(0.0, tr))
        prev_close = close
    return out


def _atr_series(ks, period=14):
    trs = _true_ranges(ks)
    if len(trs) < period:
        return []
    return [sum(trs[i-period+1:i+1]) / period for i in range(period-1, len(trs))]


def _percentile_rank(values, x):
    vals = [v for v in values if v is not None]
    if not vals or x is None:
        return None
    return sum(1 for v in vals if v <= x) / len(vals)


def _efficiency_ratio(closes, bars=24):
    if len(closes) < bars + 1:
        return None
    xs = closes[-(bars + 1):]
    net = abs(xs[-1] - xs[0])
    path = sum(abs(xs[i] - xs[i-1]) for i in range(1, len(xs)))
    return net / path if path > 0 else 0.0


def classify(ks):
    rows = list(ks or [])
    if len(rows) < 80:
        return {'regime': 'UNKNOWN', 'confidence': 0, 'reason': 'INSUFFICIENT_CANDLES', 'version': VERSION}
    closes = [_f(x.get('close')) for x in rows]
    if any(x is None for x in closes[-60:]):
        return {'regime': 'UNKNOWN', 'confidence': 0, 'reason': 'INVALID_CLOSE_SERIES', 'version': VERSION}
    px = closes[-1]
    ema20 = _ema(closes[-80:], 20)
    ema50 = _ema(closes[-120:], 50)
    atrs = _atr_series(rows[-120:], 14)
    atr = atrs[-1] if atrs else None
    atr_pct = (atr / px * 100.0) if atr is not None and px else None
    atr_rank = _percentile_rank(atrs[-60:], atr) if atrs else None
    er = _efficiency_ratio(closes, 24)
    ret24 = ((px / closes[-25]) - 1.0) * 100.0 if closes[-25] else 0.0

    prior = rows[-25:-1]
    prior_high = max(_f(x.get('high'), px) for x in prior)
    prior_low = min(_f(x.get('low'), px) for x in prior)
    breakout_up = px > prior_high
    breakout_down = px < prior_low

    trend_up = bool(ema20 is not None and ema50 is not None and px > ema20 > ema50 and ret24 > 0)
    trend_down = bool(ema20 is not None and ema50 is not None and px < ema20 < ema50 and ret24 < 0)
    efficient = er is not None and er >= 0.32
    choppy = er is not None and er <= 0.22
    high_vol = atr_rank is not None and atr_rank >= 0.80
    low_vol = atr_rank is not None and atr_rank <= 0.25

    if breakout_up and trend_up and efficient:
        regime, reason = 'VOLATILITY_EXPANSION_UP' if high_vol else 'BREAKOUT_UP', 'INDEPENDENT_RANGE_BREAK_UP'
    elif breakout_down and trend_down and efficient:
        regime, reason = 'VOLATILITY_EXPANSION_DOWN' if high_vol else 'BREAKDOWN_DOWN', 'INDEPENDENT_RANGE_BREAK_DOWN'
    elif trend_up and efficient:
        regime, reason = 'VOLATILITY_EXPANSION_UP' if high_vol else 'TREND_UP', 'EMA_STRUCTURE_AND_EFFICIENCY_UP'
    elif trend_down and efficient:
        regime, reason = 'VOLATILITY_EXPANSION_DOWN' if high_vol else 'TREND_DOWN', 'EMA_STRUCTURE_AND_EFFICIENCY_DOWN'
    elif low_vol and choppy:
        regime, reason = 'COMPRESSION', 'LOW_ATR_PERCENTILE_AND_LOW_EFFICIENCY'
    elif choppy:
        regime, reason = 'RANGE', 'LOW_DIRECTIONAL_EFFICIENCY'
    elif high_vol:
        regime, reason = 'UNSTABLE_HIGH_VOL', 'HIGH_ATR_WITHOUT_CLEAN_DIRECTION'
    else:
        regime, reason = 'TRANSITION', 'NO_STABLE_REGIME_CONSENSUS'

    evidence = 0
    evidence += 1 if efficient else 0
    evidence += 1 if high_vol or low_vol else 0
    evidence += 1 if trend_up or trend_down else 0
    evidence += 1 if breakout_up or breakout_down else 0
    confidence = min(95, 45 + evidence * 12)
    if regime in ('RANGE', 'COMPRESSION') and choppy:
        confidence = max(confidence, 69)

    return {
        'regime': regime,
        'confidence': confidence,
        'reason': reason,
        'price': px,
        'ema20': ema20,
        'ema50': ema50,
        'return_24h_pct': round(ret24, 5),
        'efficiency_ratio_24h': round(er, 6) if er is not None else None,
        'atr_pct': round(atr_pct, 6) if atr_pct is not None else None,
        'atr_percentile_60': round(atr_rank, 6) if atr_rank is not None else None,
        'breakout_up': breakout_up,
        'breakout_down': breakout_down,
        'version': VERSION,
        'research_only': True,
    }


def analyze(symbol, asset_ks, btc_ks):
    symbol = str(symbol or '').upper().replace('BINANCE:', '')
    asset = classify(asset_ks)
    btc = asset if symbol == 'BTCUSDT' else classify(btc_ks)
    return {
        'symbol': symbol,
        'asset': asset,
        'btc': btc,
        'asset_regime': asset.get('regime'),
        'btc_regime': btc.get('regime'),
        'version': VERSION,
        'independent_of_signal_direction': True,
        'shadow_only': True,
        'can_override_production': False,
    }
