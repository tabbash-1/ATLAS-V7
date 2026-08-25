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

SCHEMA = "ATLAS_HISTORICAL_SHADOW_REPLAY_V1"
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


def build_report(payload, execution_summary=None, target_cases=TARGET_CASES):
    records = list((payload or {}).get("records") or [])
    directional = [r for r in records if str(r.get("candidate_direction") or "NONE").upper() in ("LONG", "SHORT")]
    no_setup = [r for r in records if r not in directional]

    by_horizon = {}
    for h in HORIZONS:
        by_horizon[h] = _summary(((r.get("horizons") or {}).get(h) or {}).get("directional_return_pct") for r in directional)

    by_reason = {}
    grouped = defaultdict(list)
    for r in directional:
        grouped[str(r.get("reason") or "UNKNOWN")].append(r)
    for reason, rows in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        vals = [((r.get("horizons") or {}).get("24h") or {}).get("directional_return_pct") for r in rows]
        by_reason[reason] = {"records": len(rows), "at_24h": _summary(vals)}

    by_score_band = {}
    banded = defaultdict(list)
    for r in directional:
        banded[_score_band(r.get("score"))].append(r)
    for band in ("LT_60", "60_67", "68_74", "75_PLUS", "NO_SCORE"):
        rows = banded.get(band, [])
        vals = [((r.get("horizons") or {}).get("24h") or {}).get("directional_return_pct") for r in rows]
        by_score_band[band] = {"records": len(rows), "at_24h": _summary(vals)}

    by_state = {}
    stated = defaultdict(list)
    for r in records:
        stated[_state(r)].append(r)
    for state, rows in sorted(stated.items()):
        vals = [((r.get("horizons") or {}).get("24h") or {}).get("directional_return_pct") for r in rows]
        by_state[state] = {"records": len(rows), "at_24h": _summary(vals)}

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

    matured_24h = by_horizon["24h"]["n"]
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
            "directional_24h_matured": matured_24h,
            "target_reached": matured_24h >= int(target_cases),
            "remaining_to_target": max(0, int(target_cases) - matured_24h),
        },
        "directional_forward_performance": by_horizon,
        "by_wait_reason_24h": by_reason,
        "by_score_band_24h": by_score_band,
        "by_opportunity_state_24h": by_state,
        "directional_blocker_counts": dict(blocker_counts.most_common()),
        "obstacle_reason_counts": dict(obstacle_counts.most_common()),
        "no_setup_market_move_context": no_setup_moves,
        "production_threshold_changed": False,
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
