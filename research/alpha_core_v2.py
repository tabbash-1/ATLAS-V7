"""ATLAS Alpha Core V2 — regime-adaptive 4–12H direction challenger.

Research/shadow only. This module replaces the old idea of a single additive
score with an explicit decision chain:

market state -> swing thesis -> entry timing -> BTC context -> LONG/SHORT/WAIT

The output contains an evidence distribution for LONG/SHORT/WAIT. The
distribution is deliberately marked *uncalibrated*: it is a normalized evidence
summary, not a claimed empirical probability until forward calibration proves
otherwise.

It cannot change Production, Final Trade Gate, thresholds, trade geometry, the
paper portfolio, or live execution.
"""
from __future__ import annotations

import math
from historical_core_4_12h_replay import atr, direction, ema, rsi

VERSION = "ATLAS_ALPHA_CORE_V2_REGIME_ADAPTIVE"
HOUR_MS = 60 * 60 * 1000
DIRECTIONS = ("LONG", "SHORT")
SAFETY = {
    "research_only": True,
    "shadow_only": True,
    "analysis_only": True,
    "live_execution": False,
    "production_effect": "NONE",
    "can_override_production": False,
    "can_override_final_gate": False,
    "can_change_threshold": False,
    "can_create_trade": False,
}


def _f(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def opposite(side):
    return "SHORT" if side == "LONG" else "LONG" if side == "SHORT" else None


def resample_closed(rows, hours, as_of_ms):
    """Build complete, contiguous UTC-aligned HTF candles only."""
    width = int(hours) * HOUR_MS
    buckets = {}
    for row in rows or []:
        t = int(row["t"])
        start = (t // width) * width
        if start + width > int(as_of_ms):
            continue
        buckets.setdefault(start, []).append(row)
    out = []
    for start, items in sorted(buckets.items()):
        items = sorted(items, key=lambda x: int(x["t"]))
        expected = [start + i * HOUR_MS for i in range(int(hours))]
        if len(items) != int(hours) or [int(x["t"]) for x in items] != expected:
            continue
        out.append({
            "t": start,
            "o": _f(items[0]["o"]),
            "h": max(_f(x["h"]) for x in items),
            "l": min(_f(x["l"]) for x in items),
            "c": _f(items[-1]["c"]),
            "v": sum(_f(x.get("v")) for x in items),
        })
    return out


def _recent_move(hist, bars, a):
    if not a or a <= 0 or len(hist) <= bars:
        return {"side": None, "move": 0.0, "move_atr": 0.0}
    move = _f(hist[-1]["c"]) - _f(hist[-1-bars]["c"])
    move_atr = move / a
    side = "LONG" if move > 0 else "SHORT" if move < 0 else None
    return {"side": side, "move": move, "move_atr": move_atr}


def _efficiency(hist, bars=12):
    seq = list(hist or [])
    if len(seq) <= bars:
        return 0.0
    closes = [_f(x["c"]) for x in seq[-(bars+1):]]
    travel = sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes)))
    if travel <= 1e-12:
        return 0.0
    return abs(closes[-1] - closes[0]) / travel


def _volume_ratio(hist, lookback=20):
    if len(hist or []) < 2:
        return 1.0
    current = _f(hist[-1].get("v"))
    base = [_f(x.get("v")) for x in hist[-(lookback+1):-1]]
    base = [x for x in base if x >= 0]
    avg = sum(base) / len(base) if base else 0.0
    return current / avg if avg > 0 else 1.0


def _extension_atr(hist, a):
    if not hist or not a or a <= 0:
        return None
    closes = [_f(x["c"]) for x in hist]
    e20 = ema(closes[-80:], 20) if len(closes) >= 20 else None
    if e20 is None:
        return None
    return abs(closes[-1] - float(e20)) / float(a)


def _btc_context(btc_hist, as_of_ms):
    if not btc_hist:
        return {"d1": None, "d4": None, "d12": None}
    eligible = [x for x in btc_hist if int(x["t"]) + HOUR_MS <= int(as_of_ms)]
    if len(eligible) < 55:
        return {"d1": None, "d4": None, "d12": None}
    return {
        "d1": direction(eligible),
        "d4": direction(resample_closed(eligible, 4, as_of_ms)),
        "d12": direction(resample_closed(eligible, 12, as_of_ms)),
    }


def build_context(hist, decision_time_ms=None, btc_hist=None, symbol=None):
    hist = list(hist or [])
    if not hist:
        return None
    as_of = int(decision_time_ms if decision_time_ms is not None else int(hist[-1]["t"]) + HOUR_MS)
    closed = [x for x in hist if int(x["t"]) + HOUR_MS <= as_of]
    if len(closed) < 55:
        return None

    a = atr(closed, 14)
    if not a or a <= 0:
        return None
    h4 = resample_closed(closed, 4, as_of)
    h12 = resample_closed(closed, 12, as_of)
    h24 = resample_closed(closed, 24, as_of)
    closes = [_f(x["c"]) for x in closed]
    move4 = _recent_move(closed, 4, a)
    move12 = _recent_move(closed, 12, a)
    btc = _btc_context(btc_hist, as_of)

    return {
        "symbol": str(symbol or "").upper(),
        "as_of_ms": as_of,
        "d1": direction(closed),
        "d4": direction(h4),
        "d12": direction(h12),
        "d24": direction(h24),
        "recent_4h_side": move4["side"],
        "move4_atr": move4["move_atr"],
        "move12_atr": move12["move_atr"],
        "atr14": float(a),
        "rsi14": rsi(closes, 14),
        "extension_atr": _extension_atr(closed, a),
        "volume_ratio": _volume_ratio(closed),
        "efficiency12": _efficiency(closed, 12),
        "btc_d1": btc["d1"],
        "btc_d4": btc["d4"],
        "btc_d12": btc["d12"],
    }


def classify_regime(ctx):
    if not ctx:
        return "INSUFFICIENT"
    d4, d12, d24 = ctx.get("d4"), ctx.get("d12"), ctx.get("d24")
    m4 = abs(_f(ctx.get("move4_atr")))
    vr = _f(ctx.get("volume_ratio"), 1.0)
    eff = _f(ctx.get("efficiency12"))

    if d12 in DIRECTIONS and d4 == opposite(d12) and m4 >= 0.35:
        return "PULLBACK"
    if d4 in DIRECTIONS and d4 == d12:
        if m4 >= 0.75 and vr >= 0.90:
            return "BREAKOUT"
        if d24 in (None, d4):
            return "TREND"
    if eff <= 0.35 and ctx.get("recent_4h_side") in DIRECTIONS:
        return "RANGE"
    return "TRANSITION"


def _btc_blockers(ctx, side, regime):
    symbol = str(ctx.get("symbol") or "").upper()
    if not symbol or symbol == "BTCUSDT":
        return []
    opp = opposite(side)
    blockers = []
    if ctx.get("btc_d4") == opp:
        blockers.append("BTC_4H_OPPOSES")
    if regime in {"TREND", "BREAKOUT", "PULLBACK"} and ctx.get("btc_d12") == opp:
        blockers.append("BTC_12H_OPPOSES")
    return blockers


def route_context(ctx):
    """Return a transparent rule-based thesis from frozen point-in-time context."""
    if not ctx:
        return {"decision": "WAIT", "regime": "INSUFFICIENT", "playbook": None,
                "blockers": ["INSUFFICIENT_CONTEXT"], "evidence": []}

    regime = classify_regime(ctx)
    d1, d4, d12 = ctx.get("d1"), ctx.get("d4"), ctx.get("d12")
    move4 = _f(ctx.get("move4_atr"))
    extension = ctx.get("extension_atr")
    extension = _f(extension, 99.0) if extension is not None else 99.0
    vr = _f(ctx.get("volume_ratio"), 1.0)
    rs = ctx.get("rsi14")
    rs = _f(rs, 50.0)
    blockers, evidence = [], []
    side, playbook = None, None

    if regime == "PULLBACK":
        side = d12 if d12 in DIRECTIONS else None
        playbook = "12H_THESIS_4H_PULLBACK_RESUMPTION"
        if side:
            evidence += ["12H_THESIS", "4H_OPPOSING_PULLBACK"]
            if d1 == side:
                evidence.append("1H_RESUMPTION")
            else:
                blockers.append("1H_RESUMPTION_MISSING")
            if extension > 1.25:
                blockers.append("ENTRY_OVEREXTENDED")

    elif regime == "BREAKOUT":
        side = d4 if d4 in DIRECTIONS else None
        playbook = "4H_12H_BREAKOUT_CONTINUATION"
        if side:
            evidence += ["4H_12H_ALIGNED", "MEANINGFUL_4H_EXPANSION"]
            if d1 == side:
                evidence.append("1H_CONFIRMATION")
            else:
                blockers.append("1H_CONFIRMATION_MISSING")
            if vr >= 0.90:
                evidence.append("VOLUME_NOT_WEAK")
            else:
                blockers.append("VOLUME_WEAK")
            if extension > 1.50:
                blockers.append("BREAKOUT_OVEREXTENDED")

    elif regime == "TREND":
        side = d12 if d12 in DIRECTIONS else None
        playbook = "HTF_TREND_CONTINUATION"
        if side:
            evidence.append("4H_12H_ALIGNED")
            if d1 == side:
                evidence.append("1H_CONFIRMATION")
            else:
                blockers.append("1H_CONFIRMATION_MISSING")
            if abs(move4) > 1.00:
                blockers.append("TREND_ENTRY_TOO_LATE")
            if extension > 1.00:
                blockers.append("TREND_ENTRY_OVEREXTENDED")

    elif regime == "RANGE":
        recent = ctx.get("recent_4h_side")
        side = opposite(recent)
        playbook = "4H_RANGE_MEAN_REVERSION"
        if side:
            evidence += ["LOW_12H_EFFICIENCY", "FADE_RECENT_4H_MOVE"]
            if abs(move4) < 0.50:
                blockers.append("4H_MOVE_TOO_SMALL_TO_FADE")
            if d1 == side:
                evidence.append("1H_REVERSAL_CONFIRMATION")
            else:
                blockers.append("1H_REVERSAL_CONFIRMATION_MISSING")
            if side == "LONG" and rs > 55:
                blockers.append("RSI_NOT_SUPPORTIVE_FOR_LONG_FADE")
            if side == "SHORT" and rs < 45:
                blockers.append("RSI_NOT_SUPPORTIVE_FOR_SHORT_FADE")

    else:
        blockers.append("REGIME_TRANSITION_UNRESOLVED")

    if side not in DIRECTIONS:
        blockers.append("DIRECTION_UNRESOLVED")
    else:
        blockers.extend(_btc_blockers(ctx, side, regime))

    blockers = list(dict.fromkeys(blockers))
    decision = side if side in DIRECTIONS and not blockers else "WAIT"
    return {
        "decision": decision,
        "candidate_direction": side if side in DIRECTIONS else None,
        "regime": regime,
        "playbook": playbook,
        "blockers": blockers,
        "evidence": evidence,
    }


def _evidence_distribution(ctx, routed):
    """Normalize evidence strength; not an empirically calibrated probability."""
    scores = {"LONG": 0.25, "SHORT": 0.25, "WAIT": 0.50}
    side = routed.get("candidate_direction")
    regime = routed.get("regime")
    if side in DIRECTIONS:
        scores[side] += 0.80
        scores[side] += 0.16 * len(routed.get("evidence") or [])
        if regime in {"PULLBACK", "BREAKOUT"}:
            scores[side] += 0.20
    scores["WAIT"] += 0.28 * len(routed.get("blockers") or [])
    if regime == "TRANSITION":
        scores["WAIT"] += 0.60
    mx = max(scores.values())
    ex = {k: math.exp(v - mx) for k, v in scores.items()}
    den = sum(ex.values())
    return {k: round(ex[k] / den, 6) for k in ("LONG", "SHORT", "WAIT")}


def analyze(hist, decision_time_ms=None, btc_hist=None, symbol=None):
    ctx = build_context(hist, decision_time_ms, btc_hist, symbol)
    routed = route_context(ctx)
    out = {
        "version": VERSION,
        **routed,
        "evidence_distribution": _evidence_distribution(ctx or {}, routed),
        "probability_calibrated": False,
        "probability_note": "Normalized evidence distribution only; empirical calibration requires independent forward outcomes.",
        "context": ctx,
        **SAFETY,
    }
    return out


def decision(hist, decision_time_ms=None, btc_hist=None, symbol=None):
    return analyze(hist, decision_time_ms, btc_hist, symbol)["decision"]
