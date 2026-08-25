#!/usr/bin/env python3
"""ATLAS historical decision replay over recorded WAIT outcomes.

This module does not fabricate historical inputs and does not rescore old markets
with information that was not recorded at the time. It evaluates the decisions
ATLAS actually logged, preserving direction, score, blocker and forward returns.
An optional live execution summary can be attached for side-by-side comparison.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "ATLAS_HISTORICAL_SHADOW_REPLAY_V2_HORIZON_FIT"
HORIZONS = ("1h", "3h", "6h", "12h", "24h")
TARGET_CASES = 100


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _score_band(score):
    s = _f(score)
    if s is None:
        return "NO_SCORE"
    if s < 60:
        return "LT_60"
    if s < 68:
        return "60_67"
    if s < 75:
        return "68_74"
    return "75_PLUS"


def _state(row):
    direction = str(row.get("candidate_direction") or "NONE").upper()
    if direction not in ("LONG", "SHORT"):
        return "NO_SETUP"
    score = _f(row.get("score"))
    threshold = _f(row.get("threshold")) or 68.0
    if score is not None and score >= threshold:
        return "QUALIFIED_BUT_BLOCKED"
    return "WATCH"


def _summary(values):
    vals = [x for x in (_f(v) for v in values) if x is not None]
    if not vals:
        return {"n": 0, "positive_rate_pct": None, "mean_pct": None, "median_pct": None,
                "strong_positive_rate_pct": None, "strong_negative_rate_pct": None}
    n = len(vals)
    pos = sum(v > 0 for v in vals)
    strong_pos = sum(v >= 1.0 for v in vals)
    strong_neg = sum(v <= -1.0 for v in vals)
    return {
        "n": n,
        "positive_rate_pct": round(100.0 * pos / n, 2),
        "mean_pct": round(sum(vals) / n, 4),
        "median_pct": round(statistics.median(vals), 4),
        "strong_positive_rate_pct": round(100.0 * strong_pos / n, 2),
        "strong_negative_rate_pct": round(100.0 * strong_neg / n, 2),
    }


def _horizon_fit(by_horizon, target_cases):
    target = int(target_cases)
    progress = {h: {
        "matured": int(by_horizon[h]["n"]),
        "target_reached": int(by_horizon[h]["n"]) >= target,
        "remaining": max(0, target - int(by_horizon[h]["n"])),
    } for h in HORIZONS}
    reached = [h for h in HORIZONS if progress[h]["target_reached"]]
    longest = reached[-1] if reached else None
    positive_mature = [h for h in HORIZONS if by_horizon[h]["n"] >= target and (_f(by_horizon[h]["mean_pct"]) or 0) > 0]
    recommended = "12-24H" if progress["12h"]["target_reached"] and (_f(by_horizon["12h"]["mean_pct"]) or 0) > 0 else None
    return {
        "target_by_horizon": progress,
        "longest_horizon_with_100_cases": longest,
        "positive_mean_horizons_with_100_cases": positive_mature,
        "recommended_research_horizon": recommended,
        "quick_lane": {"horizon": "1-3H", "validated_as_positive_edge": False},
        "swing_lane": {
            "horizon": "12-24H",
            "validated_12h_sample": progress["12h"]["target_reached"],
            "24h_still_immature": not progress["24h"]["target_reached"],
        },
        "interpretation": "Use 1-3h only for separately confirmed tactical entries; evaluate near-threshold directional edge on 12-24h without changing Production qualification.",
    }


def _grouped_horizon_summary(rows):
    return {
        h: _summary(((r.get("horizons") or {}).get(h) or {}).get("directional_return_pct") for r in rows)
        for h in HORIZONS
    }


def build_report(payload, execution_summary=None, target_cases=TARGET_CASES):
    records = list((payload or {}).get("records") or [])
    directional = [r for r in records if str(r.get("candidate_direction") or "NONE").upper() in ("LONG", "SHORT")]
    no_setup = [r for r in records if r not in directional]

    by_horizon = _grouped_horizon_summary(directional)

    grouped = defaultdict(list)
    for r in directional:
        grouped[str(r.get("reason") or "UNKNOWN")].append(r)
    by_reason_by_horizon = {
        reason: {"records": len(rows), "horizons": _grouped_horizon_summary(rows)}
        for reason, rows in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    }

    banded = defaultdict(list)
    for r in directional:
        banded[_score_band(r.get("score"))].append(r)
    by_score_band_by_horizon = {}
    for band in ("LT_60", "60_67", "68_74", "75_PLUS", "NO_SCORE"):
        rows = banded.get(band, [])
        by_score_band_by_horizon[band] = {
            "records": len(rows),
            "horizons": _grouped_horizon_summary(rows),
        }

    stated = defaultdict(list)
    for r in records:
        stated[_state(r)].append(r)
    by_state_by_horizon = {}
    for state, rows in sorted(stated.items()):
        directional_rows = [r for r in rows if str(r.get("candidate_direction") or "NONE").upper() in ("LONG", "SHORT")]
        by_state_by_horizon[state] = {
            "records": len(rows),
            "directional_records": len(directional_rows),
            "horizons": _grouped_horizon_summary(directional_rows),
        }

    blocker_counts = Counter(str(r.get("reason") or "UNKNOWN") for r in directional)
    obstacle_counts = Counter()
    for r in directional:
        a = r.get("score_attribution") or {}
        obstacle_counts[str(a.get("obstacle_reason") or "NONE")] += 1

    no_setup_moves = {}
    for h in HORIZONS:
        changes = [abs(_f(((r.get("horizons") or {}).get(h) or {}).get("change_pct")) or 0.0) for r in no_setup if ((r.get("horizons") or {}).get(h) or {}).get("change_pct") is not None]
        no_setup_moves[h] = {
            "n": len(changes),
            "mean_abs_move_pct": round(sum(changes) / len(changes), 4) if changes else None,
            "move_ge_1pct_rate_pct": round(100.0 * sum(v >= 1.0 for v in changes) / len(changes), 2) if changes else None,
        }

    fit = _horizon_fit(by_horizon, target_cases)
    matured_24h = by_horizon["24h"]["n"]
    matured_12h = by_horizon["12h"]["n"]
    report = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_generated_at": (payload or {}).get("generated_at"),
        "methodology": "Replay of recorded ATLAS decisions and their recorded forward outcomes; no look-ahead rescoring and no threshold mutation.",
        "target_cases": int(target_cases),
        "progress": {
            "all_wait_records": len(records),
            "directional_shadow_records": len(directional),
            "no_setup_records": len(no_setup),
            "directional_12h_matured": matured_12h,
            "directional_24h_matured": matured_24h,
            "target_reached_12h": matured_12h >= int(target_cases),
            "target_reached_24h": matured_24h >= int(target_cases),
            "remaining_to_target_24h": max(0, int(target_cases) - matured_24h),
            "target_reached_any_horizon": any(x["target_reached"] for x in fit["target_by_horizon"].values()),
        },
        "horizon_fit": fit,
        "directional_forward_performance": by_horizon,
        "by_wait_reason_by_horizon": by_reason_by_horizon,
        "by_score_band_by_horizon": by_score_band_by_horizon,
        "by_opportunity_state_by_horizon": by_state_by_horizon,
        # Compatibility keys retained for existing consumers.
        "by_wait_reason_24h": {k: {"records": v["records"], "at_24h": v["horizons"]["24h"]} for k, v in by_reason_by_horizon.items()},
        "by_score_band_24h": {k: {"records": v["records"], "at_24h": v["horizons"]["24h"]} for k, v in by_score_band_by_horizon.items()},
        "by_opportunity_state_24h": {k: {"records": v["records"], "at_24h": v["horizons"]["24h"]} for k, v in by_state_by_horizon.items()},
        "directional_blocker_counts": dict(blocker_counts.most_common()),
        "obstacle_reason_counts": dict(obstacle_counts.most_common()),
        "no_setup_market_move_context": no_setup_moves,
        "production_threshold_changed": False,
        "production_threshold": 68,
        "research_only": True,
    }
    if execution_summary is not None:
        report["live_execution_comparison"] = execution_summary
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wait-outcomes", default="status/wait-outcomes.json")
    p.add_argument("--execution-summary", default=None)
    p.add_argument("--output", default="status/historical-shadow-replay.json")
    p.add_argument("--target", type=int, default=TARGET_CASES)
    args = p.parse_args()

    wait = json.loads(Path(args.wait_outcomes).read_text(encoding="utf-8"))
    execution = None
    if args.execution_summary and Path(args.execution_summary).exists():
        execution = json.loads(Path(args.execution_summary).read_text(encoding="utf-8"))
    report = build_report(wait, execution_summary=execution, target_cases=args.target)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(report["progress"], sort_keys=True))


if __name__ == "__main__":
    main()
