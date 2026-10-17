"""ATLAS indicator attribution audit V2.

Research only. Measures frozen factor associations separately for every symbol and
side over 730 days, after modeled 10 bps round-trip cost. Adds chronological
stability folds so one recent regime cannot masquerade as a durable edge.
It does not change Production, threshold 68, Final Trade Gate, or execute trades.
"""
from __future__ import annotations

import json
import statistics
from historical_core_4_12h_replay import fetch_1h, resample, direction, rsi, atr, settle

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ZECUSDT"]
DAYS = 730
COST_BPS = 10
KEYS = ["f_1h", "f_rsi", "f_structure", "f_volume"]
MIN_COMBO_N = 30
MIN_ROBUST_N = 100


def pf(vals):
    pos = sum(x for x in vals if x > 0)
    neg = abs(sum(x for x in vals if x <= 0))
    return round(pos / neg, 4) if neg else ("INF" if pos else 0)


def stats(rows):
    vals = [x["net_r"] for x in rows]
    return {
        "n": len(vals),
        "positive_pct": round(100 * sum(x > 0 for x in vals) / len(vals), 2) if vals else 0,
        "avg_r": round(statistics.mean(vals), 4) if vals else 0,
        "net_r": round(sum(vals), 4),
        "profit_factor": pf(vals),
    }


def cost_r(entry, risk):
    return (COST_BPS / 10000.0) * entry / risk if risk else 0.0


def build(symbol):
    rows = fetch_1h(symbol, DAYS)
    out = []
    i = 720
    while i < len(rows) - 12:
        hist = rows[: i + 1]
        r4 = resample(hist, 4)
        r12 = resample(hist, 12)
        d4 = direction(r4)
        d12 = direction(r12)
        d1 = direction(hist)
        if not d4 or d4 != d12:
            i += 4
            continue
        side = d4
        a = atr(hist)
        if not a:
            i += 4
            continue
        entry = hist[-1]["c"]
        stop = entry - 1.5 * a if side == "LONG" else entry + 1.5 * a
        target = entry + 3.0 * a if side == "LONG" else entry - 3.0 * a
        sig = {"side": side, "entry": entry, "stop": stop, "target": target}
        gross, outcome = settle(sig, rows[i + 1 : i + 13])
        risk = abs(entry - stop)
        rs = rsi([x["c"] for x in hist])
        recent4 = r4[-8:]
        f_1h = d1 == side
        f_rsi = rs is not None and ((side == "LONG" and 52 <= rs <= 75) or (side == "SHORT" and 25 <= rs <= 48))
        f_structure = (
            (side == "LONG" and recent4[-1]["c"] > max(x["h"] for x in recent4[-4:-1]))
            or (side == "SHORT" and recent4[-1]["c"] < min(x["l"] for x in recent4[-4:-1]))
        )
        vols = [x["v"] for x in hist[-25:-1]]
        f_volume = bool(vols and hist[-1]["v"] >= statistics.mean(vols))
        out.append(
            {
                "t": int(hist[-1]["t"]),
                "symbol": symbol,
                "side": side,
                "f_1h": f_1h,
                "f_rsi": f_rsi,
                "f_structure": f_structure,
                "f_volume": f_volume,
                "gross_r": gross,
                "net_r": gross - cost_r(entry, risk),
                "outcome": outcome,
            }
        )
        i += 4
    return out


def compare(rows, key):
    on = [x for x in rows if x[key]]
    off = [x for x in rows if not x[key]]
    a, b = stats(on), stats(off)
    return {
        "on": a,
        "off": b,
        "uplift_avg_r": round(a["avg_r"] - b["avg_r"], 4),
        "uplift_positive_pct": round(a["positive_pct"] - b["positive_pct"], 2),
    }


def fold_stats(rows, keys):
    subset = sorted((x for x in rows if all(x[k] for k in keys)), key=lambda x: x["t"])
    if not subset:
        return []
    n = len(subset)
    folds = []
    for j in range(4):
        lo = (n * j) // 4
        hi = (n * (j + 1)) // 4
        folds.append(stats(subset[lo:hi]))
    return folds


def combinations(rows):
    out = []
    for mask in range(1, 16):
        ks = [KEYS[j] for j in range(4) if mask & (1 << j)]
        subset = [x for x in rows if all(x[k] for k in ks)]
        if len(subset) < MIN_COMBO_N:
            continue
        s = stats(subset)
        folds = fold_stats(rows, ks)
        profitable_folds = sum(f["n"] and f["avg_r"] > 0 and (f["profit_factor"] == "INF" or f["profit_factor"] > 1) for f in folds)
        stable = (
            s["n"] >= MIN_ROBUST_N
            and s["avg_r"] > 0
            and (s["profit_factor"] == "INF" or s["profit_factor"] >= 1.10)
            and profitable_folds >= 3
        )
        out.append({
            "factors": ks,
            **s,
            "profitable_folds_4": profitable_folds,
            "folds": folds,
            "retrospective_stability_candidate": bool(stable),
        })
    def rank(x):
        p = x["profit_factor"] if isinstance(x["profit_factor"], float) else 99.0
        return (x["retrospective_stability_candidate"], x["avg_r"], p, x["n"])
    return sorted(out, key=rank, reverse=True)


def report(rows):
    combos = combinations(rows)
    return {
        "all_htf_aligned": stats(rows),
        "factors": {k: compare(rows, k) for k in KEYS},
        "top_combinations_min_n30": combos[:10],
        "stable_candidates": [x for x in combos if x["retrospective_stability_candidate"]],
    }


def main():
    allrows = []
    by_symbol_side = {}
    for symbol in SYMBOLS:
        rows = build(symbol)
        allrows.extend(rows)
        by_symbol_side[symbol] = {
            side: report([x for x in rows if x["side"] == side])
            for side in ("LONG", "SHORT")
        }
    result = {
        "schema": "ATLAS_INDICATOR_ATTRIBUTION_AUDIT_V2_SYMBOL_SIDE",
        "research_only": True,
        "paper_only": True,
        "live_execution": False,
        "can_override_production": False,
        "production_threshold_unchanged": 68,
        "days": DAYS,
        "cost_bps": COST_BPS,
        "important_note": (
            "Retrospective association and chronological stability only, not causal or forward proof. "
            "HTF 4H/12H alignment is the sampling prerequisite. No Production rule may be changed from this output alone."
        ),
        "by_symbol_side": by_symbol_side,
    }
    print("ATLAS_INDICATOR_ATTRIBUTION_V2=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
