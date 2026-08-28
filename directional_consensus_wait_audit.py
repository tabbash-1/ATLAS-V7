#!/usr/bin/env python3
"""Research-only audit of ATLAS NO_DIRECTIONAL_CONSENSUS WAIT states.

Uses the already-collected status/wait-outcomes.json forward outcomes. It asks:
1) what 2-vs-2 vote conflicts dominate;
2) whether WAIT usually avoided chop or missed meaningful moves;
3) whether two fixed, predeclared tie-breakers (trend-side and momentum-side)
   have stable forward value.

This script never alters Production, threshold 68, scoring weights, or execution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

SCHEMA = "ATLAS_DIRECTIONAL_CONSENSUS_WAIT_AUDIT_V1"
HORIZONS = ("1h", "3h", "6h", "12h", "24h")


def fnum(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def parse_time(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def side(flag):
    if flag is None:
        return "?"
    return "L" if flag else "S"


def vote_state(record):
    c = record.get("decision_context") or {}
    px = fnum(record.get("wait_price"))
    ema20 = fnum(c.get("ema20"))
    ema50 = fnum(c.get("ema50"))
    rsi = fnum(c.get("rsi14"))
    mom = fnum(c.get("momentum_24h_pct"))
    if None in (px, ema20, ema50, rsi, mom):
        return None
    flags = {
        "price_vs_ema20": px >= ema20,
        "ema20_vs_ema50": ema20 >= ema50,
        "rsi50": rsi >= 50.0,
        "momentum24": mom >= 0.0,
    }
    long_votes = sum(flags.values())
    short_votes = 4 - long_votes
    return {
        "flags": flags,
        "long_votes_rebuilt": long_votes,
        "short_votes_rebuilt": short_votes,
        "pattern": "P%s-T%s-R%s-M%s" % tuple(side(flags[k]) for k in ("price_vs_ema20", "ema20_vs_ema50", "rsi50", "momentum24")),
        "trend_side": "LONG" if flags["ema20_vs_ema50"] else "SHORT",
        "momentum_side": "LONG" if flags["momentum24"] else "SHORT",
        "price_side": "LONG" if flags["price_vs_ema20"] else "SHORT",
        "rsi_side": "LONG" if flags["rsi50"] else "SHORT",
    }


def directional_return(change_pct, direction):
    x = fnum(change_pct)
    if x is None or direction not in ("LONG", "SHORT"):
        return None
    return x if direction == "LONG" else -x


def de_duplicate(records):
    """One earliest NO_DIRECTIONAL_CONSENSUS observation per symbol UTC hour."""
    chosen = {}
    for r in records:
        if r.get("reason") != "NO_DIRECTIONAL_CONSENSUS":
            continue
        ts = parse_time(r.get("wait_at"))
        symbol = r.get("symbol")
        if ts is None or not symbol:
            continue
        key = (symbol, ts.replace(minute=0, second=0, microsecond=0).isoformat())
        prev = chosen.get(key)
        if prev is None or ts < parse_time(prev.get("wait_at")):
            chosen[key] = r
    return sorted(chosen.values(), key=lambda r: parse_time(r.get("wait_at")))


def terminal_market_stats(episodes, horizon):
    values = []
    abs_values = []
    max_excursions = []
    for e in episodes:
        h = (e.get("horizons") or {}).get(horizon) or {}
        ch = fnum(h.get("change_pct"))
        if ch is None:
            continue
        values.append(ch)
        abs_values.append(abs(ch))
        up = abs(fnum(h.get("max_up_pct"), 0.0) or 0.0)
        down = abs(fnum(h.get("max_down_pct"), 0.0) or 0.0)
        max_excursions.append(max(up, down))
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean_abs_terminal_move_pct": round(mean(abs_values), 4),
        "median_abs_terminal_move_pct": round(median(abs_values), 4),
        "terminal_move_ge_0_5_pct": sum(x >= 0.5 for x in abs_values),
        "terminal_move_ge_1_pct": sum(x >= 1.0 for x in abs_values),
        "terminal_move_ge_2_pct": sum(x >= 2.0 for x in abs_values),
        "chop_lt_0_5_pct": sum(x < 0.5 for x in abs_values),
        "mean_max_excursion_pct": round(mean(max_excursions), 4),
    }


def rule_stats(episodes, horizon, rule):
    vals = []
    for e in episodes:
        h = (e.get("horizons") or {}).get(horizon) or {}
        ch = fnum(h.get("change_pct"))
        vs = e.get("vote_state") or {}
        direction = vs.get(rule)
        dr = directional_return(ch, direction)
        if dr is not None:
            vals.append(dr)
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean_directional_return_pct": round(mean(vals), 4),
        "median_directional_return_pct": round(median(vals), 4),
        "win_rate_pct": round(100.0 * sum(x > 0 for x in vals) / len(vals), 2),
        "non_loss_rate_pct": round(100.0 * sum(x >= 0 for x in vals) / len(vals), 2),
        "gain_ge_1_pct": sum(x >= 1.0 for x in vals),
        "loss_le_minus_1_pct": sum(x <= -1.0 for x in vals),
        "best_pct": round(max(vals), 4),
        "worst_pct": round(min(vals), 4),
    }


def split_time(episodes, fraction=0.60):
    n = len(episodes)
    cut = max(1, min(n - 1, int(n * fraction))) if n >= 2 else n
    return episodes[:cut], episodes[cut:]


def jackknife(episodes, horizon, rule):
    symbols = sorted({e.get("symbol") for e in episodes if e.get("symbol")})
    rows = []
    for omitted in symbols:
        subset = [e for e in episodes if e.get("symbol") != omitted]
        s = rule_stats(subset, horizon, rule)
        rows.append({"omitted_symbol": omitted, **s})
    valid = [x for x in rows if x.get("n")]
    return {
        "folds": rows,
        "positive_mean_folds": sum((x.get("mean_directional_return_pct") or 0) > 0 for x in valid),
        "win_rate_ge_50_folds": sum((x.get("win_rate_pct") or 0) >= 50 for x in valid),
        "fold_count": len(valid),
    }


def pattern_stats(episodes):
    groups = defaultdict(list)
    for e in episodes:
        p = (e.get("vote_state") or {}).get("pattern", "UNKNOWN")
        groups[p].append(e)
    out = {}
    for p, xs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        item = {"n": len(xs), "symbols": dict(Counter(e.get("symbol") for e in xs))}
        for h in ("1h", "3h", "12h", "24h"):
            item[h] = terminal_market_stats(xs, h)
        out[p] = item
    return out


def robustness(episodes, rule):
    train, holdout = split_time(episodes)
    out = {"train_n": len(train), "holdout_n": len(holdout), "horizons": {}}
    for h in ("1h", "3h", "12h", "24h"):
        tr = rule_stats(train, h, rule)
        ho = rule_stats(holdout, h, rule)
        jk = jackknife(episodes, h, rule)
        stable = bool(
            tr.get("n", 0) >= 5 and ho.get("n", 0) >= 5
            and (tr.get("mean_directional_return_pct") or 0) > 0
            and (ho.get("mean_directional_return_pct") or 0) > 0
            and (tr.get("median_directional_return_pct") or 0) >= 0
            and (ho.get("median_directional_return_pct") or 0) >= 0
            and jk.get("fold_count", 0) > 0
            and jk.get("positive_mean_folds", 0) / jk.get("fold_count", 1) >= 0.75
        )
        out["horizons"][h] = {"train": tr, "holdout": ho, "jackknife": jk, "stable_positive": stable}
    return out


def audit(payload):
    raw_records = payload.get("records") or []
    episodes = de_duplicate(raw_records)
    usable = []
    rebuild_mismatch = 0
    stored_ties = 0
    for r in episodes:
        vs = vote_state(r)
        if vs is None:
            continue
        c = r.get("decision_context") or {}
        sl = c.get("direction_votes_long")
        ss = c.get("direction_votes_short")
        if sl == 2 and ss == 2:
            stored_ties += 1
        if sl is not None and ss is not None and (int(sl) != vs["long_votes_rebuilt"] or int(ss) != vs["short_votes_rebuilt"]):
            rebuild_mismatch += 1
        x = dict(r)
        x["vote_state"] = vs
        usable.append(x)

    actual_ties = [e for e in usable if e["vote_state"]["long_votes_rebuilt"] == 2 and e["vote_state"]["short_votes_rebuilt"] == 2]
    # Analyze exact 2-2 conflicts only; other no-consensus shapes remain reported
    # as coverage gaps rather than silently mixed into the result.
    episodes = actual_ties

    market = {h: terminal_market_stats(episodes, h) for h in HORIZONS}
    rules = {
        "trend_side": {h: rule_stats(episodes, h, "trend_side") for h in HORIZONS},
        "momentum_side": {h: rule_stats(episodes, h, "momentum_side") for h in HORIZONS},
    }
    robust = {r: robustness(episodes, r) for r in ("trend_side", "momentum_side")}

    stable = []
    for rule, result in robust.items():
        for h, detail in result["horizons"].items():
            if detail.get("stable_positive"):
                stable.append({"rule": rule, "horizon": h})

    if stable:
        next_decision = "A predefined tie-breaker shows stable-positive evidence in at least one horizon. Keep Production unchanged; build a prospective shadow lane only for the exact stable rule+horizon before any gate change."
    else:
        next_decision = "No predefined tie-breaker is robust enough. Preserve NO_DIRECTIONAL_CONSENSUS WAIT and investigate whether specific conflict patterns, not a global tie-breaker, explain missed opportunity."

    return {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_schema": payload.get("schema"),
        "purpose": "Determine whether NO_DIRECTIONAL_CONSENSUS WAIT is protective or systematically misses directional opportunity using existing forward outcomes.",
        "guardrails": {
            "research_only": True,
            "production_threshold": 68,
            "production_changed": False,
            "auto_promotion": False,
            "live_execution": False,
        },
        "coverage": {
            "raw_wait_outcome_records": len(raw_records),
            "unique_no_consensus_symbol_hours": len(de_duplicate(raw_records)),
            "with_rebuildable_votes": len(usable),
            "exact_2_2_episodes": len(episodes),
            "stored_2_2_episodes": stored_ties,
            "vote_rebuild_mismatch": rebuild_mismatch,
        },
        "wait_baseline_market_movement": market,
        "fixed_tie_breakers": rules,
        "chronological_and_symbol_robustness": robust,
        "conflict_patterns": pattern_stats(episodes),
        "stable_positive_candidates": stable,
        "next_decision": next_decision,
        "interpretation": {
            "wait_baseline": "WAIT has zero trading return; market movement statistics quantify opportunity cost/risk after the wait state.",
            "trend_side": "Hypothetical direction follows EMA20 vs EMA50 only; it is not a Production recommendation.",
            "momentum_side": "Hypothetical direction follows 24h momentum sign only; it is not a Production recommendation.",
            "anti_overfit": "Rules were fixed before seeing this audit. Results use one earliest record per symbol-hour, a 60/40 chronological split, and leave-one-symbol-out checks.",
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="status/wait-outcomes.json")
    ap.add_argument("--output", default="status/directional-consensus-wait-audit.json")
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text())
    report = audit(payload)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({
        "schema": report["schema"],
        "coverage": report["coverage"],
        "wait_baseline_market_movement": report["wait_baseline_market_movement"],
        "stable_positive_candidates": report["stable_positive_candidates"],
        "next_decision": report["next_decision"],
    }, indent=2))


if __name__ == "__main__":
    main()
