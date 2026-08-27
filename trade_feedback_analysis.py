#!/usr/bin/env python3
"""Research-only analyzer for exported ATLAS trade feedback datasets.

This module intentionally cannot change Production thresholds or scoring. It
summarizes closed trade outcomes and descriptive evidence attribution only.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

MIN_PRELIM = 10
MIN_SERIOUS = 20
CLOSED_STATES = {"STOPPED", "TP1 HIT", "TP2 HIT"}


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def stats(rows):
    vals = [_f(r.get("r_multiple")) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "win_rate_pct": None, "mean_r": None, "median_r": None, "net_pnl_usdt": 0.0}
    return {
        "n": len(vals),
        "win_rate_pct": round(100 * sum(v > 0 for v in vals) / len(vals), 2),
        "mean_r": round(sum(vals) / len(vals), 4),
        "median_r": round(statistics.median(vals), 4),
        "net_pnl_usdt": round(sum(_f(r.get("pnl_usdt")) or 0 for r in rows), 4),
    }


def tier(n):
    if n >= MIN_SERIOUS:
        return "SERIOUS_CANDIDATE"
    if n >= MIN_PRELIM:
        return "PRELIMINARY"
    return "HYPOTHESIS"


def build_report(payload):
    records = list((payload or {}).get("records") or [])
    closed = [r for r in records if str(r.get("state") or "").upper() in CLOSED_STATES and _f(r.get("r_multiple")) is not None]
    grouped_symbol = defaultdict(list)
    grouped_direction = defaultdict(list)
    grouped_mode = defaultdict(list)
    factor = defaultdict(lambda: {"positive": [], "negative": []})
    for r in closed:
        grouped_symbol[str(r.get("symbol") or "UNKNOWN")].append(r)
        grouped_direction[str(r.get("direction") or "UNKNOWN")].append(r)
        grouped_mode[str(r.get("entry_mode") or "UNKNOWN")].append(r)
        for e in r.get("evidence") or []:
            name = str(e.get("name") or "")
            value = _f(e.get("value"))
            if not name or value is None or value == 0:
                continue
            factor[name]["positive" if value > 0 else "negative"].append(r)

    evidence = {}
    for name, sides in sorted(factor.items()):
        pos, neg = stats(sides["positive"]), stats(sides["negative"])
        delta = None
        if pos["mean_r"] is not None and neg["mean_r"] is not None:
            delta = round(pos["mean_r"] - neg["mean_r"], 4)
        evidence[name] = {
            "positive": pos,
            "negative": neg,
            "delta_mean_r": delta,
            "enough_for_split_review": pos["n"] >= 5 and neg["n"] >= 5,
        }

    overall = stats(closed)
    return {
        "schema": "ATLAS_TRADE_FEEDBACK_RESEARCH_V1",
        "research_only": True,
        "auto_promotion_enabled": False,
        "production_threshold_changed": False,
        "production_score_adjustment": 0,
        "saved_records": len(records),
        "closed_records": len(closed),
        "overall": overall,
        "research_tier": tier(overall["n"]),
        "by_symbol": {k: stats(v) for k, v in sorted(grouped_symbol.items())},
        "by_direction": {k: stats(v) for k, v in sorted(grouped_direction.items())},
        "by_entry_mode": {k: stats(v) for k, v in sorted(grouped_mode.items())},
        "evidence_attribution": evidence,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("--output", default="status/trade-feedback-research.json")
    a = p.parse_args()
    payload = json.loads(Path(a.dataset).read_text())
    report = build_report(payload)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"closed": report["closed_records"], "tier": report["research_tier"]}, sort_keys=True))


if __name__ == "__main__":
    main()
