"""Prospective settlement for ATLAS Adaptive Evidence shadow candidates.

Research/paper only. Settles only observations that were recorded prospectively by
adaptive_evidence_live_snapshot.py. It never changes Production, threshold 68, or
Final Trade Gate and cannot execute trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import statistics
import time
import urllib.parse
import urllib.request

SCHEMA = "ATLAS_ADAPTIVE_EVIDENCE_OUTCOME_V1"
BUNDLE_SCHEMA = "ATLAS_ADAPTIVE_EVIDENCE_OUTCOME_BUNDLE_V1"
HORIZON_H = 12
COST_BPS = 10


def fetch_window_1h(symbol, start_ms, end_ms):
    q = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": "1h",
        "startTime": int(start_ms),
        "endTime": int(end_ms),
        "limit": 100,
    })
    url = "https://data-api.binance.vision/api/v3/klines?" + q
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    return [
        {"t": int(k[0]), "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])}
        for k in data
    ]


def cost_r(entry, stop, cost_bps=COST_BPS):
    risk = abs(float(entry) - float(stop))
    if risk <= 0:
        return 0.0
    return (float(cost_bps) / 10000.0) * float(entry) / risk


def settle_geometry(observation, future_rows, now_ms=None):
    """Settle one prospective candidate. Returns None until resolvable/mature."""
    g = observation.get("prospective_geometry")
    verdict = observation.get("shadow_verdict") or {}
    if verdict.get("decision") != "SHADOW_CANDIDATE" or not g:
        return None
    side = str(verdict.get("direction") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return None
    entry = float(g["entry_reference"])
    stop = float(g["stop"])
    target = float(g["target_2r"])
    close_ms = int(observation["decision_bar_close_ms"])
    horizon_ms = int(g.get("horizon_h", HORIZON_H)) * 3600_000
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)

    eligible = [r for r in future_rows if int(r["t"]) >= close_ms and int(r["t"]) < close_ms + horizon_ms]
    for c in eligible:
        hit_stop = c["l"] <= stop if side == "LONG" else c["h"] >= stop
        hit_target = c["h"] >= target if side == "LONG" else c["l"] <= target
        if hit_stop and hit_target:
            gross_r, outcome = -1.0, "LOSS_BOTH_STOP_FIRST"
            break
        if hit_stop:
            gross_r, outcome = -1.0, "LOSS"
            break
        if hit_target:
            gross_r, outcome = 2.0, "WIN_TP2"
            break
    else:
        if now_ms < close_ms + horizon_ms or len(eligible) < int(g.get("horizon_h", HORIZON_H)):
            return None
        last = eligible[-1]["c"]
        risk = abs(entry - stop)
        gross_r = (last - entry) / risk if side == "LONG" else (entry - last) / risk
        gross_r = max(-1.0, min(2.0, gross_r))
        outcome = "EXPIRED"

    modeled_cost_r = cost_r(entry, stop, g.get("modeled_round_trip_cost_bps", COST_BPS))
    net_r = gross_r - modeled_cost_r
    return {
        "schema": SCHEMA,
        "observation_id": observation["observation_id"],
        "symbol": observation["symbol"],
        "direction": side,
        "grade": verdict.get("grade"),
        "decision_bar_close_ms": close_ms,
        "settled_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "outcome": outcome,
        "gross_r": round(gross_r, 6),
        "modeled_cost_r": round(modeled_cost_r, 6),
        "net_r": round(net_r, 6),
        "positive_after_cost": bool(net_r > 0),
        "research_only": True,
        "paper_only": True,
        "live_execution": False,
        "can_override_production": False,
        "production_threshold_unchanged": 68,
    }


def _read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def summarize(rows):
    if not rows:
        return {"n": 0, "positive_after_cost": 0, "positive_pct": 0.0, "avg_net_r": 0.0, "net_r": 0.0, "profit_factor": 0.0}
    rs = [float(r["net_r"]) for r in rows]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gp, gl = sum(wins), abs(sum(losses))
    pf = gp / gl if gl else ("INF" if gp else 0.0)
    return {
        "n": len(rows),
        "positive_after_cost": len(wins),
        "positive_pct": round(100 * len(wins) / len(rows), 2),
        "avg_net_r": round(statistics.mean(rs), 6),
        "net_r": round(sum(rs), 6),
        "profit_factor": round(pf, 6) if isinstance(pf, float) else pf,
    }


def record(status_dir="status", now_ms=None, fetcher=fetch_window_1h):
    root = pathlib.Path(status_dir)
    obs_path = root / "history" / "adaptive-evidence-shadow-observations.jsonl"
    out_path = root / "history" / "adaptive-evidence-shadow-outcomes.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    observations = _read_jsonl(obs_path)
    outcomes = _read_jsonl(out_path)
    known = {r.get("observation_id") for r in outcomes}
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)

    for obs in observations:
        if obs.get("observation_id") in known:
            continue
        if (obs.get("shadow_verdict") or {}).get("decision") != "SHADOW_CANDIDATE":
            continue
        close_ms = int(obs["decision_bar_close_ms"])
        end_ms = min(now_ms, close_ms + HORIZON_H * 3600_000) - 1
        if end_ms < close_ms:
            continue
        future = fetcher(obs["symbol"], close_ms, end_ms)
        settled = settle_geometry(obs, future, now_ms=now_ms)
        if settled:
            with out_path.open("a") as f:
                f.write(json.dumps(settled, sort_keys=True, separators=(",", ":")) + "\n")
            outcomes.append(settled)
            known.add(settled["observation_id"])

    by_model = {}
    for r in outcomes:
        key = f"{r['symbol']}|{r['direction']}|{r.get('grade') or 'NA'}"
        by_model.setdefault(key, []).append(r)
    latest = {
        "schema": BUNDLE_SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_only": True,
        "paper_only": True,
        "live_execution": False,
        "can_override_production": False,
        "production_threshold_unchanged": 68,
        "cost_basis_bps": COST_BPS,
        "settled_candidates": len(outcomes),
        "overall": summarize(outcomes),
        "by_model": {k: summarize(v) for k, v in sorted(by_model.items())},
        "interpretation": "PROSPECTIVE_SHADOW_EVIDENCE_ONLY_NOT_PRODUCTION_PROOF",
    }
    (root / "adaptive-evidence-shadow-outcomes-latest.json").write_text(json.dumps(latest, indent=2, sort_keys=True))
    return latest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status-dir", default="status")
    args = ap.parse_args()
    result = record(args.status_dir)
    print("ATLAS_ADAPTIVE_EVIDENCE_OUTCOMES=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
