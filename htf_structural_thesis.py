"""ATLAS hierarchical 4-12H structural thesis gate.

Direction authority belongs to 12H + 4H. 1H may confirm or delay an entry but
cannot reverse the higher-timeframe thesis. 1D is macro context. The module
never changes Production score/threshold and never enables live execution.
"""
from __future__ import annotations

import urllib.parse

VERSION = "HTF_STRUCTURAL_THESIS_V1"
PRODUCT_HORIZON = "4-12H"
TIMEFRAMES = ("1h", "4h", "12h", "1d")
AUTHORITY_TIMEFRAMES = ("12h", "4h")


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _ema(vals, n):
    vals = [float(x) for x in vals if x is not None]
    if not vals:
        return None
    k = 2.0 / (n + 1.0)
    out = vals[0]
    for v in vals[1:]:
        out = v * k + out * (1.0 - k)
    return out


def _atr(rows, n=14):
    if len(rows) <= n:
        return None
    trs = []
    for i in range(len(rows) - n, len(rows)):
        h = _f(rows[i].get("high")); l = _f(rows[i].get("low")); pc = _f(rows[i-1].get("close"))
        if h is None or l is None or pc is None:
            continue
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(trs) / len(trs) if trs else None


def _swings(rows, left=2, right=2):
    highs, lows = [], []
    for i in range(left, len(rows)-right):
        h = _f(rows[i].get("high")); l = _f(rows[i].get("low"))
        if h is not None:
            peers = [_f(rows[j].get("high"), h) for j in range(i-left, i+right+1) if j != i]
            if all(h >= x for x in peers): highs.append({"index": i, "price": h, "time": rows[i].get("time")})
        if l is not None:
            peers = [_f(rows[j].get("low"), l) for j in range(i-left, i+right+1) if j != i]
            if all(l <= x for x in peers): lows.append({"index": i, "price": l, "time": rows[i].get("time")})
    return highs, lows


def _structure_bias(highs, lows):
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL", "INSUFFICIENT_SWINGS"
    h0, h1 = highs[-2]["price"], highs[-1]["price"]
    l0, l1 = lows[-2]["price"], lows[-1]["price"]
    if h1 > h0 and l1 > l0:
        return "LONG", "HH_HL"
    if h1 < h0 and l1 < l0:
        return "SHORT", "LH_LL"
    return "NEUTRAL", "MIXED_STRUCTURE"


def analyze_frame(rows, timeframe):
    rows = list(rows or [])
    if len(rows) < 60:
        return {"timeframe": timeframe, "ok": False, "bias": "UNKNOWN", "reason": "INSUFFICIENT_CANDLES", "candles": len(rows)}
    closes = [_f(x.get("close")) for x in rows]
    closes = [x for x in closes if x is not None]
    if len(closes) < 60:
        return {"timeframe": timeframe, "ok": False, "bias": "UNKNOWN", "reason": "INVALID_CANDLES", "candles": len(closes)}
    px = closes[-1]
    ema20 = _ema(closes[-100:], 20); ema50 = _ema(closes[-160:], 50)
    highs, lows = _swings(rows[-160:])
    sbias, structure = _structure_bias(highs, lows)
    trend = "NEUTRAL"
    if ema20 is not None and ema50 is not None:
        if px > ema20 > ema50: trend = "LONG"
        elif px < ema20 < ema50: trend = "SHORT"
    if sbias == trend and sbias in ("LONG", "SHORT"):
        bias, confidence = sbias, "STRONG"
    elif sbias in ("LONG", "SHORT") and trend == "NEUTRAL":
        bias, confidence = sbias, "STRUCTURE"
    elif trend in ("LONG", "SHORT") and sbias == "NEUTRAL":
        bias, confidence = trend, "TREND_ONLY"
    else:
        bias, confidence = "NEUTRAL", "CONFLICT"
    prev_high = highs[-1]["price"] if highs else None
    prev_low = lows[-1]["price"] if lows else None
    breakout = "NONE"
    if prev_high is not None and px > prev_high: breakout = "BREAKOUT_UP"
    if prev_low is not None and px < prev_low: breakout = "BREAKDOWN_DOWN"
    atr = _atr(rows, 14)
    return {
        "timeframe": timeframe, "ok": True, "bias": bias, "confidence": confidence,
        "structure": structure, "trend": trend, "price": px,
        "ema20": round(ema20, 10) if ema20 is not None else None,
        "ema50": round(ema50, 10) if ema50 is not None else None,
        "atr14": round(atr, 10) if atr is not None else None,
        "last_swing_high": prev_high, "last_swing_low": prev_low,
        "breakout_state": breakout,
    }


def _nearest_levels(frame_states, px):
    supports, resistances = [], []
    for tf in ("4h", "12h", "1d"):
        s = frame_states.get(tf) or {}
        for key in ("last_swing_low", "last_swing_high", "ema20", "ema50"):
            val = _f(s.get(key))
            if val is None or val <= 0: continue
            item = {"price": val, "timeframe": tf, "source": key.upper()}
            if val < px: supports.append(item)
            elif val > px: resistances.append(item)
    supports.sort(key=lambda x: x["price"], reverse=True)
    resistances.sort(key=lambda x: x["price"])
    return (supports[0] if supports else None), (resistances[0] if resistances else None)


def analyze_frames(frames, proposed_direction=None):
    states = {tf: analyze_frame(frames.get(tf) or [], tf) for tf in TIMEFRAMES}
    missing = [tf for tf in TIMEFRAMES if not states[tf].get("ok")]
    if missing:
        return {
            "version": VERSION, "status": "BLOCK", "direction": None,
            "reason": "HTF_DATA_INCOMPLETE", "missing_timeframes": missing,
            "frames": states, "product_horizon": PRODUCT_HORIZON,
            "can_flip_from_1h_only": False, "live_execution": False,
        }
    b4 = states["4h"]["bias"]; b12 = states["12h"]["bias"]; b1 = states["1h"]["bias"]; bd = states["1d"]["bias"]
    if b4 not in ("LONG", "SHORT") or b12 not in ("LONG", "SHORT") or b4 != b12:
        direction = None
        status, reason = "WAIT", "4H_12H_NOT_ALIGNED"
    else:
        direction = b4
        if proposed_direction in ("LONG", "SHORT") and proposed_direction != direction:
            status, reason = "WAIT", "PROPOSED_DIRECTION_OPPOSES_HTF"
        elif b1 in ("LONG", "SHORT") and b1 != direction:
            status, reason = "WAIT", "1H_NOT_CONFIRMED_HTF"
        else:
            status, reason = "PASS", "HTF_ALIGNED_1H_CONFIRMED_OR_NEUTRAL"
    px = _f(states["1h"].get("price"))
    support, resistance = _nearest_levels(states, px) if px else (None, None)
    if direction == "LONG":
        invalidation = support
        trigger_level = _f(states["4h"].get("last_swing_high"))
        trigger = "1H close/hold confirms LONG while 4H+12H remain bullish" + (f"; watch 4H swing {trigger_level:.10g}" if trigger_level else "")
    elif direction == "SHORT":
        invalidation = resistance
        trigger_level = _f(states["4h"].get("last_swing_low"))
        trigger = "1H close/hold confirms SHORT while 4H+12H remain bearish" + (f"; watch 4H swing {trigger_level:.10g}" if trigger_level else "")
    else:
        invalidation = None; trigger_level = None
        trigger = "Wait for 4H and 12H to align on the same structural direction"
    return {
        "version": VERSION, "status": status, "direction": direction, "reason": reason,
        "product_horizon": PRODUCT_HORIZON, "authority_timeframes": list(AUTHORITY_TIMEFRAMES),
        "context_timeframe": "1d", "confirmation_timeframe": "1h",
        "daily_context": bd, "frames": states,
        "nearest_support": support, "nearest_resistance": resistance,
        "trigger": trigger, "trigger_level": trigger_level,
        "invalidation_level": invalidation.get("price") if invalidation else None,
        "invalidation_source": invalidation,
        "decision_persistence_rule": "1H may delay to WAIT but cannot reverse LONG/SHORT unless 4H+12H thesis changes or structural invalidation is breached.",
        "can_flip_from_1h_only": False, "score_changed": False, "threshold_changed": False,
        "research_only": False, "analysis_only": True, "live_execution": False,
    }


def _fetch_klines(atlas, symbol, interval, limit=220):
    path = f"/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval={urllib.parse.quote(interval)}&limit={int(limit)}"
    urls = [
        "https://data-api.binance.vision" + path,
        "https://api-gcp.binance.com" + path,
        "https://api1.binance.com" + path,
        "https://api2.binance.com" + path,
        "https://api3.binance.com" + path,
        "https://api4.binance.com" + path,
        "https://api.binance.com" + path,
    ]
    raw = atlas.get_json_fallback(urls, "spot")
    if not isinstance(raw, list):
        raise RuntimeError(f"Invalid {interval} kline payload")
    return [{"time": int(x[0]), "open": _f(x[1]), "high": _f(x[2]), "low": _f(x[3]), "close": _f(x[4]), "volume": _f(x[5])} for x in raw]


def build_live_thesis(atlas, symbol, proposed_direction=None):
    frames = {}
    errors = {}
    for tf in TIMEFRAMES:
        try:
            frames[tf] = atlas._spot_klines(symbol, 220) if tf == "1h" else _fetch_klines(atlas, symbol, tf, 220)
        except Exception as exc:
            frames[tf] = []
            errors[tf] = f"{type(exc).__name__}: {exc}"
    thesis = analyze_frames(frames, proposed_direction)
    thesis["symbol"] = symbol
    thesis["fetch_errors"] = errors
    return thesis


def install(atlas):
    if getattr(atlas, "_HTF_STRUCTURAL_THESIS_INSTALLED", False):
        return getattr(atlas, "HTF_STRUCTURAL_THESIS_STATE", {"enabled": True, "version": VERSION})
    original = atlas.production_decision

    def wrapped(symbol):
        row = original(symbol)
        if not isinstance(row, dict) or not row.get("ok"):
            return row
        proposed = row.get("candidate_direction")
        thesis = build_live_thesis(atlas, str(symbol or row.get("symbol") or "").upper().replace("BINANCE:", ""), proposed)
        row["htf_thesis"] = thesis
        row["htf_thesis_version"] = VERSION
        row["htf_score_preserved"] = True
        row["htf_threshold_preserved"] = True
        if thesis.get("status") != "PASS":
            row["pre_htf_actionable_decision"] = row.get("actionable_decision")
            row["pre_htf_actionable_reason"] = row.get("actionable_reason")
            row["actionable_decision"] = "WAIT"
            row["actionable_reason"] = thesis.get("reason") or "HTF_THESIS_NOT_READY"
            row["analysis_ready"] = False
            row["setup_ready"] = False
            row["opportunity_state"] = "WATCH"
            row["opportunity_state_reason"] = row["actionable_reason"]
        plan = dict(row.get("trade_plan") or {})
        if thesis.get("trigger"):
            plan["htf_entry_trigger"] = thesis["trigger"]
            if not plan.get("entry_trigger"): plan["entry_trigger"] = thesis["trigger"]
        if thesis.get("invalidation_level") is not None:
            plan["htf_invalidation_level"] = thesis["invalidation_level"]
            plan["htf_invalidation_source"] = thesis.get("invalidation_source")
        plan["decision_persistence_rule"] = thesis.get("decision_persistence_rule")
        row["trade_plan"] = plan
        matrix = dict(row.get("timeframe_matrix") or {})
        matrix["htf_structural_thesis"] = thesis
        row["timeframe_matrix"] = matrix
        return row

    atlas.production_decision = wrapped
    atlas._HTF_STRUCTURAL_THESIS_INSTALLED = True
    atlas.HTF_STRUCTURAL_THESIS_STATE = {
        "enabled": True, "version": VERSION, "product_horizon": PRODUCT_HORIZON,
        "direction_authority": list(AUTHORITY_TIMEFRAMES), "confirmation": "1h", "context": "1d",
        "one_hour_can_flip_direction": False, "score_threshold_unchanged": True,
        "analysis_only": True, "live_execution": False,
    }
    return atlas.HTF_STRUCTURAL_THESIS_STATE
