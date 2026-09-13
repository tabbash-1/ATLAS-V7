"""ATLAS Adaptive Evidence prospective comparison scorecard.

Keeps Adaptive Shadow and canonical Production-forward evidence in separate lanes.
It never merges samples, never changes Production, and never claims superiority
before the predeclared minimum prospective sample is reached.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

SCHEMA = "ATLAS_ADAPTIVE_EVIDENCE_COMPARISON_SCORECARD_V1"
MIN_ADAPTIVE_FOR_COMPARISON = 10
MIN_CANONICAL_FOR_COMPARISON = 10


def _load(path):
    return json.loads(pathlib.Path(path).read_text())


def _status(n, minimum):
    return "SUFFICIENT_FOR_INITIAL_COMPARISON" if int(n) >= int(minimum) else "EARLY_INSUFFICIENT_SAMPLE"


def build(adaptive, canonical):
    a = adaptive.get("overall") or {}
    c = canonical.get("path_summary") or (canonical.get("summary") or {}).get("portfolio") or {}
    an = int(a.get("n", adaptive.get("settled_candidates", 0)) or 0)
    cn = int(c.get("entries", c.get("closed", 0)) or 0)
    allowed = an >= MIN_ADAPTIVE_FOR_COMPARISON and cn >= MIN_CANONICAL_FOR_COMPARISON

    adaptive_lane = {
        "authority": "ADAPTIVE_EVIDENCE_SHADOW_PROSPECTIVE",
        "n": an,
        "sample_status": _status(an, MIN_ADAPTIVE_FOR_COMPARISON),
        "positive_pct_after_cost": float(a.get("positive_pct", 0.0) or 0.0),
        "avg_net_r_after_cost": float(a.get("avg_net_r", 0.0) or 0.0),
        "net_r_after_cost": float(a.get("net_r", 0.0) or 0.0),
        "profit_factor_after_cost": a.get("profit_factor", 0.0),
        "cost_basis_bps": adaptive.get("cost_basis_bps"),
        "research_only": True,
        "paper_only": True,
    }
    canonical_lane = {
        "authority": "FINAL_TRADE_GATE_CANONICAL_PAPER_PORTFOLIO",
        "n": cn,
        "sample_status": _status(cn, MIN_CANONICAL_FOR_COMPARISON),
        "win_rate_pct_gross": float(c.get("win_rate_pct", 0.0) or 0.0),
        "avg_r_gross": float(c.get("avg_r", 0.0) or 0.0),
        "net_r_gross": float(c.get("net_r", 0.0) or 0.0),
        "profit_factor_gross": c.get("profit_factor", 0.0),
        "max_drawdown_pct": float(c.get("max_drawdown_pct", 0.0) or 0.0),
        "cost_basis": "GROSS_CANONICAL_COSTS_NOT_DEDUCTED",
        "paper_only": True,
    }

    if not allowed:
        verdict = "INSUFFICIENT_DATA"
        reason = f"Need at least {MIN_ADAPTIVE_FOR_COMPARISON} settled Adaptive shadow candidates and {MIN_CANONICAL_FOR_COMPARISON} canonical trades before initial comparison."
    else:
        verdict = "COMPARISON_ALLOWED_NOT_CAUSAL_PROOF"
        reason = "Both lanes reached the predeclared initial sample floor; lanes remain non-equivalent and must not be pooled."

    return {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "product_horizon": "4-12H",
        "production_threshold_unchanged": 68,
        "live_execution": False,
        "can_override_production": False,
        "lanes_are_separate": True,
        "samples_are_not_pooled": True,
        "adaptive_shadow_forward": adaptive_lane,
        "canonical_production_forward": canonical_lane,
        "comparison": {
            "allowed": allowed,
            "verdict": verdict,
            "reason": reason,
            "minimum_adaptive_n": MIN_ADAPTIVE_FOR_COMPARISON,
            "minimum_canonical_n": MIN_CANONICAL_FOR_COMPARISON,
            "important_note": "Adaptive metrics are modeled after 10bps costs; canonical portfolio metrics are gross. Direct return/PF superiority must not be claimed from these unmatched cost bases or eligibility populations."
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adaptive", default="status/adaptive-evidence-shadow-outcomes-latest.json")
    ap.add_argument("--canonical", default="status/canonical-outcomes-latest.json")
    ap.add_argument("--out", default="status/adaptive-evidence-comparison-latest.json")
    args = ap.parse_args()
    result = build(_load(args.adaptive), _load(args.canonical))
    pathlib.Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True))
    print("ATLAS_ADAPTIVE_EVIDENCE_COMPARISON=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
