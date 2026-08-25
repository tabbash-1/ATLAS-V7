"""ATLAS Production continuation-aware scoring overlay.

Adds market-wide continuation evidence without lowering the canonical Production
threshold. Strong directional momentum, broad crypto participation and sane RSI
can reduce an otherwise excessive nearby-structure penalty and can extend the
structural target beyond a nearby prior swing when continuation evidence is
strong. Weak breadth, weak momentum or blow-off RSI never receive the relief.
"""
from __future__ import annotations

import time

VERSION = "PROD_CONTINUATION_SCORING_V1"
BREADTH_TTL_SECONDS = 45
MIN_BREADTH_ASSETS = 5


def _f(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def momentum_adjustment(direction, momentum_24h_pct, rsi=None):
    mom = _f(momentum_24h_pct, 0.0) or 0.0
    aligned = mom if direction == "LONG" else -mom
    if aligned < 1.5:
        return 0
    bonus = 2 if aligned < 3.0 else 4 if aligned < 5.0 else 6
    r = _f(rsi)
    if r is not None and ((direction == "LONG" and r >= 82) or (direction == "SHORT" and r <= 18)):
        return 0
    return bonus


def extension_guard_adjustment(direction, rsi):
    r = _f(rsi)
    if r is None:
        return 0, "NO_RSI_GUARD"
    if direction == "LONG" and r >= 82:
        return -4, "BLOWOFF_RSI_LONG"
    if direction == "SHORT" and r <= 18:
        return -4, "BLOWOFF_RSI_SHORT"
    return 0, "RSI_SANE"


def breadth_adjustment(direction, breadth):
    if not isinstance(breadth, dict) or int(breadth.get("available") or 0) < MIN_BREADTH_ASSETS:
        return 0
    frac = _f(breadth.get("long_fraction" if direction == "LONG" else "short_fraction"), 0.0) or 0.0
    if frac >= 0.75:
        return 3
    if frac >= 0.625:
        return 2
    if frac >= 0.50:
        return 1
    return 0


def continuation_context(direction, votes, momentum_24h_pct, rsi, breadth):
    frac = _f((breadth or {}).get("long_fraction" if direction == "LONG" else "short_fraction"), 0.0) or 0.0
    mom = _f(momentum_24h_pct, 0.0) or 0.0
    aligned_mom = mom if direction == "LONG" else -mom
    sane_rsi = True
    r = _f(rsi)
    if r is not None:
        sane_rsi = (r < 82) if direction == "LONG" else (r > 18)
    strong = bool(
        int(votes or 0) == 4
        and aligned_mom >= 3.0
        and int((breadth or {}).get("available") or 0) >= MIN_BREADTH_ASSETS
        and frac >= 0.625
        and sane_rsi
    )
    return {
        "strong": strong,
        "direction": direction,
        "votes": int(votes or 0),
        "aligned_momentum_24h_pct": round(aligned_mom, 3),
        "breadth_fraction": round(frac, 3),
        "breadth_available": int((breadth or {}).get("available") or 0),
        "rsi_sane": sane_rsi,
        "rule": "4_VOTES_AND_MOMENTUM>=3PCT_AND_BREADTH>=62.5PCT_AND_RSI_NOT_BLOWOFF",
    }


def relieved_obstacle_adjustment(original_adjustment, strong_continuation):
    original = _f(original_adjustment, 0.0) or 0.0
    if not strong_continuation:
        return original, 0, "UNCHANGED"
    if original <= -8:
        return -3, 5, "CONTINUATION_RELIEF_VERY_CLOSE_STRUCTURE"
    if original <= -4:
        return 0, 4, "CONTINUATION_RELIEF_CLOSE_STRUCTURE"
    return original, 0, "NO_RELIEF_NEEDED"


def _compute_breadth(atlas):
    long_count = short_count = available = 0
    details = {}
    for symbol in tuple(getattr(atlas, "ON_DEMAND_SYMBOLS", ())):
        try:
            ks = atlas._spot_klines(symbol)
            if len(ks) < 50:
                continue
            closes = [float(x["close"]) for x in ks]
            px = closes[-1]
            ema20 = atlas._ema(closes[-80:], 20)
            ema50 = atlas._ema(closes[-120:], 50)
            mom24 = ((px / closes[-25]) - 1) * 100 if len(closes) >= 25 and closes[-25] else 0.0
            long_aligned = bool(px >= ema20 >= ema50 and mom24 > 0)
            short_aligned = bool(px <= ema20 <= ema50 and mom24 < 0)
            available += 1
            long_count += int(long_aligned)
            short_count += int(short_aligned)
            details[symbol] = {"momentum_24h_pct": round(mom24, 3), "long_aligned": long_aligned, "short_aligned": short_aligned}
        except Exception:
            continue
    return {
        "available": available,
        "long_count": long_count,
        "short_count": short_count,
        "long_fraction": round(long_count / available, 4) if available else 0.0,
        "short_fraction": round(short_count / available, 4) if available else 0.0,
        "details": details,
    }


def install(atlas):
    original = atlas.cloud_score_symbol
    cache = {"ts": 0.0, "value": None}

    def breadth():
        now = time.time()
        if cache["value"] is None or now - cache["ts"] >= BREADTH_TTL_SECONDS:
            cache["value"] = _compute_breadth(atlas)
            cache["ts"] = now
        return cache["value"]

    def score(symbol, btc_ks):
        row = original(symbol, btc_ks)
        if not isinstance(row, dict):
            return row
        direction = row.get("direction")
        if direction not in ("LONG", "SHORT"):
            return row

        ks = atlas._spot_klines(symbol)
        closes = [float(x["close"]) for x in ks]
        rsi = atlas._rsi(closes, 14) if closes else None
        atr = atlas._atr(ks, 14) if ks else None
        mom24 = _f(row.get("momentum_24h_pct"), 0.0) or 0.0
        votes = int(row.get("direction_votes") or 0)
        market = breadth()
        cont = continuation_context(direction, votes, mom24, rsi, market)

        attr = dict(row.get("score_attribution") or {})
        old_obstacle = _f(attr.get("obstacle_adjustment"), 0.0) or 0.0
        new_obstacle, relief, relief_reason = relieved_obstacle_adjustment(old_obstacle, cont["strong"])
        mom_adj = momentum_adjustment(direction, mom24, rsi)
        breadth_adj = breadth_adjustment(direction, market)
        guard_adj, guard_reason = extension_guard_adjustment(direction, rsi)

        trend = _f(attr.get("trend_base"), 0.0) or 0.0
        volume = _f(attr.get("volume_bonus"), 0.0) or 0.0
        rel = _f(attr.get("relative_strength_adjustment"), 0.0) or 0.0
        futures = _f(attr.get("futures_adjustment"), 0.0) or 0.0
        raw = trend + volume + rel + futures + new_obstacle + mom_adj + breadth_adj + guard_adj
        final = round(max(0, min(100, raw)))
        threshold = float(getattr(atlas, "CLOUD_FORWARD_MIN_SCORE", 68))

        attr.update({
            "obstacle_adjustment": round(new_obstacle, 3),
            "obstacle_adjustment_before_continuation": round(old_obstacle, 3),
            "continuation_obstacle_relief": round(relief, 3),
            "continuation_obstacle_reason": relief_reason,
            "momentum_adjustment": mom_adj,
            "market_breadth_adjustment": breadth_adj,
            "extension_guard_adjustment": guard_adj,
            "extension_guard_reason": guard_reason,
            "raw_score": round(raw, 3),
            "final_score": final,
            "formula": "trend_base + paced_volume_bonus + relative_strength_adjustment + futures_adjustment + continuation_aware_obstacle_adjustment + momentum_adjustment + market_breadth_adjustment + extension_guard_adjustment",
        })

        row["score_attribution"] = attr
        row["champion_score"] = final
        row["final_score"] = final
        row["opportunity_score"] = final
        row["playbook_score"] = final
        row["production_signal_qualified"] = bool(final >= threshold)
        row["research_champion_take"] = bool(final >= 60)
        row["champion_take"] = bool(final >= 60)
        row["execution_decision"] = f"{direction}_CANDIDATE" if final >= threshold else f"{direction}_WATCH"
        row["market_breadth"] = market
        row["continuation_context"] = cont
        row["continuation_scoring_version"] = VERSION
        row["scoring_version"] = f"{row.get('scoring_version')}+{VERSION}"

        level = _f(row.get("structural_obstacle_price"))
        distance = _f(attr.get("obstacle_distance_pct"))
        px = _f(row.get("entry"))
        if cont["strong"] and level is not None and px is not None and atr and atr > 0 and distance is not None and distance <= 1.5:
            target = level + atr * 1.4 if direction == "LONG" else level - atr * 1.4
            risk = atr * 1.2
            reward = target - px if direction == "LONG" else px - target
            rr = reward / risk if risk > 0 and reward > 0 else None
            row["structural_target"] = round(target, 10)
            row["structural_target_source"] = "CONTINUATION_EXTENSION_BEYOND_PRIOR_STRUCTURE"
            row["rr_tp2"] = round(rr, 3) if rr is not None else None
            row["playbook_primary"] = "MARKET_CONTINUATION_LONG" if direction == "LONG" else "MARKET_CONTINUATION_SHORT"

        return row

    atlas.cloud_score_symbol = score
    atlas.PRODUCTION_CONTINUATION_SCORING_STATE = {
        "enabled": True,
        "version": VERSION,
        "threshold_unchanged": True,
        "breadth_assets": list(getattr(atlas, "ON_DEMAND_SYMBOLS", ())),
    }
    return atlas.PRODUCTION_CONTINUATION_SCORING_STATE
