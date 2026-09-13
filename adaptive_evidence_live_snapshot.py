"""Prospective live shadow recorder for ATLAS Adaptive Evidence Engine V1.

Research only. Uses fully closed 1H Binance public candles, derives the same
frozen factors used by the retrospective attribution audit, and records the
Adaptive Evidence Engine verdict. It cannot alter Production or execute trades.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import statistics
import time

from adaptive_evidence_engine import VERSION as ENGINE_VERSION, evaluate
from historical_core_4_12h_replay import atr, direction, fetch_1h, resample, rsi

SCHEMA = "ATLAS_ADAPTIVE_EVIDENCE_LIVE_SNAPSHOT_V1"
SYMBOLS = ("XRPUSDT", "ZECUSDT")
HORIZON_H = 12
COST_BPS = 10


def _closed(rows, now_ms=None):
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    return [r for r in rows if int(r["t"]) + 3600_000 <= now_ms]


def _factor_state(rows, symbol):
    if len(rows) < 720:
        raise ValueError("need at least 720 fully closed 1H candles")
    r4 = resample(rows, 4)
    r12 = resample(rows, 12)
    d4 = direction(r4)
    d12 = direction(r12)
    d1 = direction(rows)
    side = d4 if d4 in {"LONG", "SHORT"} else None
    rs = rsi([x["c"] for x in rows])
    recent4 = r4[-8:]
    structure = False
    rsi_aligned = False
    if side and len(recent4) >= 4:
        structure = (
            side == "LONG" and recent4[-1]["c"] > max(x["h"] for x in recent4[-4:-1])
        ) or (
            side == "SHORT" and recent4[-1]["c"] < min(x["l"] for x in recent4[-4:-1])
        )
        if rs is not None:
            rsi_aligned = (side == "LONG" and 52 <= rs <= 75) or (side == "SHORT" and 25 <= rs <= 48)
    vols = [x["v"] for x in rows[-25:-1]]
    volume = bool(vols and rows[-1]["v"] >= statistics.mean(vols))
    return {
        "htf_4h": d4,
        "htf_12h": d12,
        "direction_1h": d1,
        "direction": side,
        "confirm_1h": bool(side and d1 == side),
        "rsi": round(rs, 4) if rs is not None else None,
        "rsi_aligned": rsi_aligned,
        "structure_break": structure,
        "volume_confirmed": volume,
    }


def build_observation(symbol, rows, now_ms=None):
    symbol = symbol.upper()
    closed = _closed(rows, now_ms)
    factors = _factor_state(closed, symbol)
    bar = closed[-1]
    direction_now = factors["direction"] or "NONE"
    verdict = evaluate(
        symbol,
        direction_now,
        htf_4h=factors["htf_4h"] or "NONE",
        htf_12h=factors["htf_12h"] or "NONE",
        confirm_1h=factors["confirm_1h"],
        rsi_aligned=factors["rsi_aligned"],
        structure_break=factors["structure_break"],
        volume_confirmed=factors["volume_confirmed"],
    )
    a = atr(closed)
    entry = float(bar["c"])
    geometry = None
    if verdict["decision"] == "SHADOW_CANDIDATE" and a and direction_now in {"LONG", "SHORT"}:
        stop = entry - 1.5 * a if direction_now == "LONG" else entry + 1.5 * a
        target = entry + 3.0 * a if direction_now == "LONG" else entry - 3.0 * a
        geometry = {
            "entry_reference": entry,
            "stop": stop,
            "target_2r": target,
            "atr_1h_14": a,
            "horizon_h": HORIZON_H,
            "modeled_round_trip_cost_bps": COST_BPS,
            "intrabar_both_hit_rule": "STOP_FIRST_CONSERVATIVE",
        }
    obs_key = f"{ENGINE_VERSION}|{symbol}|{bar['t']}"
    oid = hashlib.sha256(obs_key.encode()).hexdigest()[:24]
    captured = dt.datetime.now(dt.timezone.utc).isoformat()
    return {
        "schema": SCHEMA,
        "observation_id": oid,
        "engine_version": ENGINE_VERSION,
        "captured_at": captured,
        "decision_bar_open_ms": int(bar["t"]),
        "decision_bar_close_ms": int(bar["t"]) + 3600_000,
        "symbol": symbol,
        "market_reference_price": entry,
        "factors": factors,
        "shadow_verdict": verdict,
        "prospective_geometry": geometry,
        "research_only": True,
        "paper_only": True,
        "live_execution": False,
        "can_override_production": False,
        "production_threshold_unchanged": 68,
    }


def _load_ids(path):
    ids = set()
    if not path.exists():
        return ids
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
            if row.get("observation_id"):
                ids.add(row["observation_id"])
        except Exception:
            continue
    return ids


def capture(symbols=SYMBOLS, status_dir="status"):
    root = pathlib.Path(status_dir)
    hist = root / "history" / "adaptive-evidence-shadow-observations.jsonl"
    hist.parent.mkdir(parents=True, exist_ok=True)
    known = _load_ids(hist)
    observations = []
    for symbol in symbols:
        rows = fetch_1h(symbol, 35)
        obs = build_observation(symbol, rows)
        observations.append(obs)
        if obs["observation_id"] not in known:
            with hist.open("a") as f:
                f.write(json.dumps(obs, sort_keys=True, separators=(",", ":")) + "\n")
            known.add(obs["observation_id"])
    latest = {
        "schema": "ATLAS_ADAPTIVE_EVIDENCE_LIVE_BUNDLE_V1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "engine_version": ENGINE_VERSION,
        "research_only": True,
        "paper_only": True,
        "live_execution": False,
        "can_override_production": False,
        "production_threshold_unchanged": 68,
        "symbols": list(symbols),
        "observations": observations,
    }
    (root / "adaptive-evidence-shadow-latest.json").write_text(json.dumps(latest, indent=2, sort_keys=True))
    return latest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=list(SYMBOLS))
    ap.add_argument("--status-dir", default="status")
    args = ap.parse_args()
    result = capture(tuple(args.symbols), args.status_dir)
    print("ATLAS_ADAPTIVE_EVIDENCE_LIVE=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
