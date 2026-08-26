"""Audit which decision-time features are actually recorded in ATLAS history.

Research/governance only. This script never reads outcome files and never
reconstructs missing fields. Its purpose is to determine what the historical
Production snapshots can support without look-ahead or synthetic backfill.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
from pathlib import Path
from typing import Any

VERSION = "ATLAS_HISTORICAL_FEATURE_AUDIT_V1_NO_OUTCOMES_NO_BACKFILL"

FEATURES = {
    "direction_score": ["candidate_direction", "score", "signal_threshold"],
    "production_qualification": ["signal_qualified", "production_signal_qualified"],
    "trade_geometry": ["entry", "stop_loss", "take_profit", "risk_reward"],
    "trade_plan": ["trade_plan.entry", "trade_plan.stop_loss", "trade_plan.tp1", "trade_plan.tp2", "trade_plan.rr_tp2"],
    "market_regime": ["regime"],
    "indicators": ["indicators.ema20", "indicators.ema50", "indicators.rsi14", "indicators.atr14", "indicators.volume_ratio", "indicators.momentum_24h_pct"],
    "futures_summary": ["futures_available", "futures_provider", "futures_score"],
    "score_attribution": ["score_attribution"],
    "structural_geometry": ["structural_geometry"],
    "profit_engine_shadow": ["profit_engine_shadow"],
    "microstructure_shadow": ["microstructure_shadow"],
    "volatility_shadow": ["volatility_shadow"],
}

KEYWORDS = (
    "funding", "open_interest", "oi_", "orderbook", "order_book", "taker",
    "spread", "slippage", "depth", "microstructure", "volatility", "profit_engine",
    "regime", "atr", "rsi", "volume", "futures",
)


def get_path(obj: Any, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def present(v: Any) -> bool:
    return v is not None and v != ""


def flatten(obj: Any, prefix: str = "", depth: int = 0):
    if depth > 7:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield p
            yield from flatten(v, p, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:3]:
            yield from flatten(v, prefix + "[]", depth + 1)


def iso(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).isoformat()
    except Exception:
        return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="status/history/production-snapshots.jsonl")
    ap.add_argument("--output", default="status/historical-feature-audit.json")
    args = ap.parse_args()

    path = Path(args.input)
    snapshots = []
    malformed = 0
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            malformed += 1
            continue
        snapshots.append(row)

    feature_stats = {k: {"decision_rows_present": 0, "first_seen": None, "last_seen": None} for k in FEATURES}
    keyword_paths = collections.Counter()
    decision_rows = 0
    ok_decisions = 0
    qualified_rows = 0
    symbols = collections.Counter()
    snapshot_times = []

    for snap in snapshots:
        captured = iso(snap.get("captured_at"))
        if captured:
            snapshot_times.append(captured)
        for symbol, d in (snap.get("decisions") or {}).items():
            if not isinstance(d, dict):
                continue
            decision_rows += 1
            symbols[symbol] += 1
            if d.get("ok"):
                ok_decisions += 1
            if d.get("signal_qualified") or d.get("production_signal_qualified"):
                qualified_rows += 1
            t = iso(d.get("generated_at")) or captured
            for name, paths in FEATURES.items():
                # A group is replay-eligible only if every required path was recorded.
                if all(present(get_path(d, p)) for p in paths):
                    st = feature_stats[name]
                    st["decision_rows_present"] += 1
                    if t and (st["first_seen"] is None or t < st["first_seen"]):
                        st["first_seen"] = t
                    if t and (st["last_seen"] is None or t > st["last_seen"]):
                        st["last_seen"] = t
            for p in set(flatten(d)):
                lp = p.lower()
                if any(k in lp for k in KEYWORDS):
                    keyword_paths[p] += 1

    for st in feature_stats.values():
        st["coverage_pct_of_decision_rows"] = round(100.0 * st["decision_rows_present"] / decision_rows, 2) if decision_rows else 0.0

    # Conservative eligibility labels. Modern layers may only be called historical
    # evidence when their actual output was stored in that historical decision.
    replay = {
        "safe_recorded_features": [k for k in ("direction_score", "production_qualification", "trade_geometry", "trade_plan", "market_regime", "indicators", "futures_summary", "score_attribution", "structural_geometry") if feature_stats[k]["decision_rows_present"] > 0],
        "modern_layer_outputs_recorded": [k for k in ("profit_engine_shadow", "microstructure_shadow", "volatility_shadow") if feature_stats[k]["decision_rows_present"] > 0],
        "forbidden": [
            "Do not synthesize a missing historical modern-layer output from later state.",
            "Do not use outcome/settlement files to create decision-time features.",
            "Do not label a reconstructed row as frozen-forward evidence unless the field was actually recorded at that timestamp.",
        ],
    }

    out = {
        "schema": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": str(path),
        "research_only": True,
        "outcomes_read": False,
        "backfill_performed": False,
        "snapshot_count": len(snapshots),
        "malformed_snapshot_lines": malformed,
        "first_snapshot_at": min(snapshot_times) if snapshot_times else None,
        "last_snapshot_at": max(snapshot_times) if snapshot_times else None,
        "decision_rows": decision_rows,
        "ok_decision_rows": ok_decisions,
        "production_qualified_decision_rows": qualified_rows,
        "symbols": dict(sorted(symbols.items())),
        "feature_groups": feature_stats,
        "keyword_paths": [{"path": p, "decision_rows_present": n, "coverage_pct": round(100.0*n/decision_rows, 2) if decision_rows else 0.0} for p, n in keyword_paths.most_common(120)],
        "replay_policy": replay,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps({k: out[k] for k in ("schema", "snapshot_count", "first_snapshot_at", "last_snapshot_at", "decision_rows", "production_qualified_decision_rows")}, indent=2))


if __name__ == "__main__":
    main()
