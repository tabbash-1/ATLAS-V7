#!/usr/bin/env python3
"""ATLAS scored-WAIT attribution audit using EXISTING outcomes only.

The audit asks a narrow counterfactual question: after correcting the historical
partial-hour volume bias, which remaining V6 SCORE_BELOW_SIGNAL_THRESHOLD waits
were suppressed by each individual negative score component, and were those
suppressed observations actually profitable afterwards?

Nothing here can alter Production scoring, threshold 68, or execution.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC = Path("status/wait-outcomes.json")
OUT = Path("status/scored-wait-attribution-audit.json")
V6_PREFIX = "PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE"
FIX_TAG = "PARTIAL_VOLUME_TIME_FIX_V1"
SCHEMA = "ATLAS_SCORED_WAIT_ATTRIBUTION_AUDIT_V1"
THRESHOLD = 68.0
EPISODE_GAP = timedelta(hours=12)
HORIZONS = ("1h", "3h", "12h", "24h")
ALIASES = {
    "VERY_CLOSE": "VERY_CLOSE_PRIOR_STRUCTURE",
    "CLOSE": "CLOSE_PRIOR_STRUCTURE",
}


def fnum(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def parse_time(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def version(row):
    return str((row.get("decision_context") or {}).get("scoring_version") or "").upper()


def obstacle_reason(row):
    r = str((row.get("score_attribution") or {}).get("obstacle_reason") or "NONE").upper()
    return ALIASES.get(r, r)


def progress_from_timestamp(ts):
    if ts is None:
        return 1.0
    seconds = ts.minute * 60 + ts.second + ts.microsecond / 1_000_000
    return max(0.10, min(1.0, seconds / 3600.0))


def paced_rv(raw_rv, progress):
    raw = max(0.0, fnum(raw_rv, 0.0))
    p = max(0.10, min(1.0, fnum(progress, 1.0))
    return min(4.0, raw / p)


def volume_bonus_v6(rv):
    return min(10.0, max(0.0, (fnum(rv, 0.0) - 1.0) * 10.0))


def round_score(v):
    return int(round(max(0.0, min(100.0, fnum(v, 0.0)))))


def corrected_score(row):
    """Return score after replaying only the known partial-hour RV defect.

    Post-fix observations are left untouched. Pre-fix V6 observations receive
    only the non-negative volume-bonus delta that the paced formula would have
    supplied at the original decision timestamp.
    """
    score = fnum(row.get("score"))
    if score is None:
        return None
    ver = version(row)
    attr = row.get("score_attribution") or {}
    dc = row.get("decision_context") or {}
    ts = parse_time(row.get("wait_at"))
    raw_rv = fnum(dc.get("relative_volume"))
    if FIX_TAG in ver or raw_rv is None:
        return {
            "score": round_score(score),
            "volume_delta": 0.0,
            "raw_rv": raw_rv,
            "paced_rv": raw_rv,
            "progress": 1.0 if FIX_TAG in ver else None,
            "post_fix": FIX_TAG in ver,
        }

    p = progress_from_timestamp(ts)
    paced = paced_rv(raw_rv, p)
    old_bonus = fnum(attr.get("volume_bonus"), volume_bonus_v6(raw_rv))
    new_bonus = volume_bonus_v6(paced)
    delta = max(0.0, new_bonus - old_bonus)
    raw_score = fnum(attr.get("raw_score"), score)
    return {
        "score": round_score(raw_score + delta),
        "volume_delta": round(delta, 6),
        "raw_rv": round(raw_rv, 6),
        "paced_rv": round(paced, 6),
        "progress": round(p, 6),
        "post_fix": False,
    }


def hourly_dedupe(rows):
    """Keep the earliest observation per symbol/direction/hour."""
    chosen = {}
    for row in sorted(rows, key=lambda r: str(r.get("wait_at") or "")):
        ts = parse_time(row.get("wait_at"))
        if ts is None:
            continue
        key = (
            str(row.get("symbol") or "").upper(),
            str(row.get("candidate_direction") or "").upper(),
            ts.replace(minute=0, second=0, microsecond=0).isoformat(),
        )
        chosen.setdefault(key, row)
    return list(chosen.values())


def independent_12h(rows):
    """Conservative outcome episodes: one symbol/direction observation per 12h."""
    groups = defaultdict(list)
    for row in rows:
        ts = parse_time(row.get("wait_at"))
        d = str(row.get("candidate_direction") or "").upper()
        s = str(row.get("symbol") or "").upper()
        if ts is None or d not in {"LONG", "SHORT"}:
            continue
        groups[(s, d)].append((ts, row))
    out = []
    for items in groups.values():
        last = None
        for ts, row in sorted(items, key=lambda x: x[0]):
            if last is None or ts - last >= EPISODE_GAP:
                out.append(row)
                last = ts
    return sorted(out, key=lambda r: str(r.get("wait_at") or ""))


def directional_value(row, horizon):
    return fnum((row.get("horizons") or {}).get(horizon, {}).get("directional_return_pct"))


def stats(rows, horizon):
    vals = [directional_value(r, horizon) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "mean_pct": None, "median_pct": None, "win_rate_pct": None}
    return {
        "n": len(vals),
        "mean_pct": round(statistics.mean(vals), 4),
        "median_pct": round(statistics.median(vals), 4),
        "win_rate_pct": round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
    }


def horizon_report(rows):
    return {h: stats(rows, h) for h in HORIZONS}


def split_stability(rows, horizon):
    usable = [r for r in rows if directional_value(r, horizon) is not None]
    usable = sorted(usable, key=lambda r: str(r.get("wait_at") or ""))
    if len(usable) < 5:
        return {"n": len(usable), "eligible": False}
    cut = max(1, min(len(usable) - 1, int(len(usable) * 0.60)))
    train, holdout = usable[:cut], usable[cut:]
    train_s, hold_s = stats(train, horizon), stats(holdout, horizon)

    symbols = sorted({str(r.get("symbol") or "").upper() for r in usable})
    jackknife = []
    for symbol in symbols:
        subset = [r for r in usable if str(r.get("symbol") or "").upper() != symbol]
        s = stats(subset, horizon)
        if s["n"]:
            jackknife.append({"left_out": symbol, **s})

    positive_jackknife = sum((x.get("mean_pct") or 0) > 0 for x in jackknife)
    win50_jackknife = sum((x.get("win_rate_pct") or 0) >= 50 for x in jackknife)
    stable = bool(
        len(usable) >= 8
        and (train_s.get("mean_pct") or 0) > 0
        and (hold_s.get("mean_pct") or 0) > 0
        and (hold_s.get("win_rate_pct") or 0) >= 50
        and jackknife
        and positive_jackknife == len(jackknife)
        and win50_jackknife == len(jackknife)
    )
    return {
        "n": len(usable),
        "eligible": True,
        "train": train_s,
        "holdout": hold_s,
        "leave_one_symbol_out": {
            "tests": len(jackknife),
            "positive_mean": positive_jackknife,
            "win_rate_ge_50": win50_jackknife,
            "all_positive_and_win50": bool(jackknife and positive_jackknife == len(jackknife) and win50_jackknife == len(jackknife)),
        },
        "stable_positive": stable,
    }


def gap_bucket(row):
    gap = max(0.0, THRESHOLD - fnum(row.get("_corrected_score"), 0.0))
    if gap <= 2:
        return "1-2"
    if gap <= 4:
        return "3-4"
    if gap <= 8:
        return "5-8"
    return ">8"


def grouped(rows, keyfn):
    groups = defaultdict(list)
    for row in rows:
        groups[str(keyfn(row))].append(row)
    return {k: {"episodes": len(v), "outcomes": horizon_report(v)} for k, v in sorted(groups.items())}


def relaxation_delta(row, rule):
    attr = row.get("score_attribution") or {}
    obs = fnum(attr.get("obstacle_adjustment"), 0.0) or 0.0
    fut = fnum(attr.get("futures_adjustment"), 0.0) or 0.0
    rs = fnum(attr.get("relative_strength_adjustment"), 0.0) or 0.0
    reason = obstacle_reason(row)

    if rule == "REMOVE_CLOSE_OBSTACLE_PENALTY":
        return -obs if reason == "CLOSE_PRIOR_STRUCTURE" and obs < 0 else 0.0
    if rule == "REMOVE_VERY_CLOSE_OBSTACLE_PENALTY":
        return -obs if reason == "VERY_CLOSE_PRIOR_STRUCTURE" and obs < 0 else 0.0
    if rule == "REMOVE_ANY_OBSTACLE_PENALTY":
        return -obs if obs < 0 else 0.0
    if rule == "REMOVE_NEGATIVE_FUTURES_PENALTY":
        return -fut if fut < 0 else 0.0
    if rule == "REMOVE_OPPOSED_RELATIVE_STRENGTH_PENALTY":
        return -rs if rs < 0 else 0.0
    raise KeyError(rule)


def evaluate_relaxation(rows, rule):
    selected = []
    for row in rows:
        base = fnum(row.get("_corrected_score"))
        if base is None or base >= THRESHOLD:
            continue
        delta = relaxation_delta(row, rule)
        if delta <= 0:
            continue
        cf = round_score(base + delta)
        if cf >= THRESHOLD:
            x = dict(row)
            x["_relaxation_delta"] = round(delta, 4)
            x["_counterfactual_score"] = cf
            selected.append(x)

    outcome_eps = independent_12h(selected)
    return {
        "hourly_crossings": len(selected),
        "independent_12h_crossings": len(outcome_eps),
        "outcomes": horizon_report(outcome_eps),
        "stability": {
            "12h": split_stability(outcome_eps, "12h"),
            "24h": split_stability(outcome_eps, "24h"),
        },
        "production_change_recommended": False,
        "research_interpretation": (
            "SHADOW_CANDIDATE" if split_stability(outcome_eps, "12h").get("stable_positive") or split_stability(outcome_eps, "24h").get("stable_positive")
            else "KEEP_AS_HYPOTHESIS"
        ),
    }


def audit(payload):
    records = payload.get("records") or []
    raw_scored = []
    volume_flips = []

    for row in records:
        ver = version(row)
        if not ver.startswith(V6_PREFIX):
            continue
        if str(row.get("reason") or "") != "SCORE_BELOW_SIGNAL_THRESHOLD":
            continue
        if str(row.get("candidate_direction") or "").upper() not in {"LONG", "SHORT"}:
            continue
        corr = corrected_score(row)
        if corr is None:
            continue
        x = dict(row)
        x["_corrected_score"] = corr["score"]
        x["_volume_delta"] = corr["volume_delta"]
        x["_paced_rv"] = corr["paced_rv"]
        x["_raw_rv"] = corr["raw_rv"]
        x["_post_volume_fix"] = corr["post_fix"]
        raw_scored.append(x)
        if corr["score"] >= THRESHOLD:
            volume_flips.append(x)

    hourly = hourly_dedupe(raw_scored)
    hourly_volume_flips = [r for r in hourly if fnum(r.get("_corrected_score"), 0) >= THRESHOLD]
    remaining_hourly = [r for r in hourly if fnum(r.get("_corrected_score"), 0) < THRESHOLD]
    remaining_eps = independent_12h(remaining_hourly)

    rules = [
        "REMOVE_CLOSE_OBSTACLE_PENALTY",
        "REMOVE_VERY_CLOSE_OBSTACLE_PENALTY",
        "REMOVE_ANY_OBSTACLE_PENALTY",
        "REMOVE_NEGATIVE_FUTURES_PENALTY",
        "REMOVE_OPPOSED_RELATIVE_STRENGTH_PENALTY",
    ]
    relaxations = {rule: evaluate_relaxation(remaining_hourly, rule) for rule in rules}

    near = sorted(
        remaining_hourly,
        key=lambda r: (THRESHOLD - fnum(r.get("_corrected_score"), 0), str(r.get("wait_at") or "")),
    )[:25]
    near_threshold = []
    for r in near:
        attr = r.get("score_attribution") or {}
        near_threshold.append({
            "symbol": r.get("symbol"),
            "wait_at": r.get("wait_at"),
            "direction": r.get("candidate_direction"),
            "stored_score": r.get("score"),
            "corrected_score": r.get("_corrected_score"),
            "gap_to_68": round(THRESHOLD - fnum(r.get("_corrected_score"), 0), 3),
            "volume_fix_delta": r.get("_volume_delta"),
            "direction_votes": (r.get("decision_context") or {}).get("direction_votes"),
            "obstacle_reason": obstacle_reason(r),
            "obstacle_adjustment": attr.get("obstacle_adjustment"),
            "futures_reason": attr.get("futures_reason"),
            "futures_adjustment": attr.get("futures_adjustment"),
            "relative_strength_reason": attr.get("relative_strength_reason"),
            "relative_strength_adjustment": attr.get("relative_strength_adjustment"),
            "12h_directional_return_pct": directional_value(r, "12h"),
            "24h_directional_return_pct": directional_value(r, "24h"),
        })

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Explain remaining V6 scored WAIT after the known partial-hour volume bias is replay-corrected, using existing forward outcomes only.",
        "method": {
            "v6_scope": f"scoring_version starts {V6_PREFIX}",
            "wait_scope": "reason == SCORE_BELOW_SIGNAL_THRESHOLD and direction is LONG/SHORT",
            "hourly_dedupe": "earliest symbol/direction observation per UTC hour",
            "outcome_independence": "one symbol/direction episode every 12 hours",
            "volume_replay": "pre-fix only; paced_rv=min(4, raw_rv/max(0.10,hour_progress)); only non-negative missing volume bonus is restored",
            "counterfactuals": "one negative component relaxed at a time; no combined tuning",
            "stability": "60/40 chronological train/holdout plus leave-one-symbol-out; stable flag needs n>=8, positive train/holdout mean, holdout win>=50%, and all jackknifes positive with win>=50%",
        },
        "coverage": {
            "raw_v6_scored_wait_records": len(raw_scored),
            "hourly_v6_scored_waits": len(hourly),
            "hourly_volume_fix_crossings": len(hourly_volume_flips),
            "hourly_remaining_after_volume_fix": len(remaining_hourly),
            "independent_12h_remaining": len(remaining_eps),
        },
        "remaining_wait_outcomes": horizon_report(remaining_eps),
        "remaining_by_gap_to_threshold": grouped(remaining_eps, gap_bucket),
        "remaining_by_direction_votes": grouped(remaining_eps, lambda r: (r.get("decision_context") or {}).get("direction_votes", "UNKNOWN")),
        "remaining_by_obstacle": grouped(remaining_eps, obstacle_reason),
        "remaining_by_futures_reason": grouped(remaining_eps, lambda r: (r.get("score_attribution") or {}).get("futures_reason", "UNKNOWN")),
        "remaining_by_relative_strength_reason": grouped(remaining_eps, lambda r: (r.get("score_attribution") or {}).get("relative_strength_reason", "UNKNOWN")),
        "single_component_counterfactuals": relaxations,
        "near_threshold_examples": near_threshold,
        "guardrails": {
            "research_only": True,
            "production_threshold": THRESHOLD,
            "production_threshold_changed": False,
            "production_score_changed": False,
            "auto_promotion_enabled": False,
            "live_execution": False,
        },
        "next_decision": "Only a single-component relaxation that is stable on chronological holdout and leave-one-symbol-out may advance to a separate shadow. Otherwise keep the Production penalty unchanged.",
    }


def main():
    payload = json.loads(SRC.read_text())
    report = audit(payload)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "schema": report["schema"],
        "coverage": report["coverage"],
        "shadow_candidates": [
            k for k, v in report["single_component_counterfactuals"].items()
            if v["research_interpretation"] == "SHADOW_CANDIDATE"
        ],
        "guardrails": report["guardrails"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
