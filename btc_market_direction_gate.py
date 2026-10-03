"""BTC-first market direction gate for canonical ATLAS 4-12H analysis.

Consumes independent point-in-time regime evidence. It never changes scorer
thresholds. Strong opposing BTC regimes block altcoin analysis readiness; noisy
or transitional BTC regimes remain neutral rather than inventing direction.
"""

VERSION = "BTC_MARKET_DIRECTION_GATE_V1"
BULLISH = {"TREND_UP", "BREAKOUT_UP", "VOLATILITY_EXPANSION_UP"}
BEARISH = {"TREND_DOWN", "BREAKDOWN_DOWN", "VOLATILITY_EXPANSION_DOWN"}
MIN_CONFIDENCE = 69


def assess(symbol, direction, independent_regime):
    symbol = str(symbol or "").upper().replace("BINANCE:", "")
    if direction not in ("LONG", "SHORT"):
        return {"pass": False, "reason": "NO_DIRECTION", "version": VERSION}
    if symbol == "BTCUSDT":
        return {"pass": True, "reason": "BTC_IS_MARKET_ANCHOR", "version": VERSION}
    btc = (independent_regime or {}).get("btc") or {}
    regime = btc.get("regime")
    try: confidence = float(btc.get("confidence") or 0)
    except Exception: confidence = 0.0
    if regime in (None, "UNKNOWN"):
        return {"pass": False, "reason": "BTC_REGIME_UNAVAILABLE", "btc_regime": regime, "btc_confidence": confidence, "version": VERSION}
    if confidence < MIN_CONFIDENCE:
        return {"pass": False, "reason": "BTC_REGIME_LOW_CONFIDENCE", "btc_regime": regime, "btc_confidence": confidence, "version": VERSION}
    opposing = (direction == "LONG" and regime in BEARISH) or (direction == "SHORT" and regime in BULLISH)
    if opposing:
        return {"pass": False, "reason": "BTC_REGIME_OPPOSES_ALT_DIRECTION", "btc_regime": regime, "btc_confidence": confidence, "version": VERSION}
    return {"pass": True, "reason": "BTC_REGIME_NOT_OPPOSING", "btc_regime": regime, "btc_confidence": confidence, "version": VERSION}
