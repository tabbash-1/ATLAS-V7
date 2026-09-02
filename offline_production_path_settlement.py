#!/usr/bin/env python3
"""Offline canonical Production TP/SL path settlement.

Runs outside Render. It reads committed Production snapshots, freezes the canonical
trade-plan geometry at the first qualified observation of each contiguous signal
episode, and later settles the first SL/TP2 touch from public market candles.
Research-only: never changes Production decisions, thresholds, alerts or execution.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import pathlib
import time
import urllib.parse
import urllib.request
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
HISTORY = ROOT / "status/history/production-snapshots.jsonl"
LEDGER = ROOT / "status/history/production-path-settlement.jsonl"
LATEST = ROOT / "status/production-path-settlement-latest.json"
HORIZON_H = 12
SCHEMA = "ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V1_12H"


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def parse_time(v: str):
    return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def load_snapshots():
    out = []
    if not HISTORY.exists():
        return out
    for line in HISTORY.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            out.append((parse_time(row["captured_at"]), row))
        except Exception:
            continue
    return sorted(out, key=lambda x: x[0])


def canonical_geometry(decision: dict[str, Any]):
    if not decision.get("signal_qualified"):
        return None
    plan = decision.get("trade_plan") or {}
    direction = str(plan.get("direction") or decision.get("candidate_direction") or "").upper()
    entry = fnum(plan.get("entry"))
    stop = fnum(plan.get("stop_loss"))
    tp1 = fnum(plan.get("tp1"))
    tp2 = fnum(plan.get("tp2"))
    rr1 = fnum(plan.get("rr_tp1"))
    rr2 = fnum(plan.get("rr_tp2"))
    if direction not in {"LONG", "SHORT"} or None in (entry, stop, tp2):
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if direction == "LONG" and not (stop < entry < tp2):
        return None
    if direction == "SHORT" and not (stop > entry > tp2):
        return None
    if tp1 is None:
        tp1 = entry + risk if direction == "LONG" else entry - risk
    if rr1 is None:
        rr1 = abs(tp1 - entry) / risk
    if rr2 is None:
        rr2 = abs(tp2 - entry) / risk
    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": stop,
        "tp1": tp1,
        "tp2": tp2,
        "rr_tp1": rr1,
        "rr_tp2": rr2,
        "risk_abs": risk,
        "trade_plan_version": plan.get("version"),
        "entry_mode": plan.get("entry_mode"),
    }


def episode_id(symbol: str, captured_at: str, geometry: dict[str, Any]):
    raw = f"{symbol}|{captured_at}|{geometry['direction']}|{geometry['entry']:.12g}|{geometry['stop_loss']:.12g}|{geometry['tp2']:.12g}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def build_episodes(snapshots):
    episodes = []
    active: dict[str, dict[str, Any] | None] = {}
    for t, snap in snapshots:
        for symbol, d in (snap.get("decisions") or {}).items():
            g = canonical_geometry(d or {})
            current = active.get(symbol)
            if not g:
                active[symbol] = None
                continue
            same = bool(current and current.get("direction") == g["direction"])
            if same:
                continue
            captured = t.isoformat()
            ep = {
                "id": episode_id(symbol, captured, g),
                "symbol": symbol,
                "captured_at": captured,
                "captured_at_ms": int(t.timestamp() * 1000),
                "score": fnum(d.get("score")),
                "threshold": fnum(d.get("signal_threshold")),
                "playbook": d.get("playbook"),
                "regime": d.get("regime"),
                "execution_ready_at_capture": bool(d.get("execution_ready")),
                "geometry": g,
            }
            episodes.append(ep)
            active[symbol] = {"direction": g["direction"], "id": ep["id"]}
    return episodes


def request_json(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "ATLAS-Offline-Settlement/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def bybit_klines(symbol: str, interval: str, start_ms: int, end_ms: int):
    # Bybit returns newest first and max 1000 rows. 12h at 5m=144 rows, so one call is sufficient.
    q = urllib.parse.urlencode({"category": "linear", "symbol": symbol, "interval": interval, "start": start_ms, "end": end_ms, "limit": 1000})
    raw = request_json("https://api.bybit.com/v5/market/kline?" + q)
    rows = (((raw or {}).get("result") or {}).get("list") or [])
    out = []
    for k in rows:
        try:
            out.append({"open_time": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])})
        except Exception:
            pass
    return sorted(out, key=lambda x: x["open_time"])


def touches(c, p):
    return c["low"] <= p <= c["high"]


def event_from(candles, g):
    tp1_seen = False
    for c in candles:
        sl = touches(c, g["stop_loss"])
        tp1 = touches(c, g["tp1"])
        tp2 = touches(c, g["tp2"])
        if sl and (tp1 or tp2):
            return "AMBIGUOUS", c, tp1_seen
        if sl:
            return "SL", c, tp1_seen
        if tp2:
            return "TP2", c, True
        if tp1:
            tp1_seen = True
    return ("TP1_ONLY" if tp1_seen else "NONE"), None, tp1_seen


def excursions(candles, g):
    if not candles:
        return None, None
    entry, risk, direction = g["entry"], g["risk_abs"], g["direction"]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    if direction == "LONG":
        mfe = (max(highs) - entry) / risk
        mae = (entry - min(lows)) / risk
    else:
        mfe = (entry - min(lows)) / risk
        mae = (max(highs) - entry) / risk
    return round(mfe, 4), round(mae, 4)


def settle(ep, now_ms):
    start = int(ep["captured_at_ms"])
    maturity = start + HORIZON_H * 3600_000
    base = {**ep, "schema": SCHEMA, "research_only": True, "live_execution": False, "can_override_production": False}
    if now_ms < maturity:
        return {**base, "status": "OPEN", "terminal": False, "r_multiple": None}
    end = maturity
    try:
        candles = bybit_klines(ep["symbol"], "5", start, end)
        if not candles:
            return {**base, "status": "MARKET_DATA_ERROR", "terminal": False, "r_multiple": None, "error": "no_5m_candles"}
        ev, candle, tp1_seen = event_from(candles, ep["geometry"])
        if ev == "AMBIGUOUS" and candle:
            one = bybit_klines(ep["symbol"], "1", candle["open_time"], candle["open_time"] + 5 * 60_000 - 1)
            ev1, _, tp1_before_1m = event_from(one, ep["geometry"])
            ev = ev1 if ev1 in {"SL", "TP2"} else "AMBIGUOUS"
            tp1_seen = tp1_seen or tp1_before_1m
        mfe, mae = excursions(candles, ep["geometry"])
        if ev == "SL":
            status, r, terminal = "LOSS", -1.0, True
        elif ev == "TP2":
            status, r, terminal = "WIN_TP2", float(ep["geometry"]["rr_tp2"]), True
        elif ev == "AMBIGUOUS":
            status, r, terminal = "AMBIGUOUS", None, False
        else:
            last = candles[-1]["close"]
            g = ep["geometry"]
            directional = (last - g["entry"]) if g["direction"] == "LONG" else (g["entry"] - last)
            r = directional / g["risk_abs"]
            status, terminal = "EXPIRED_TP1" if tp1_seen else "EXPIRED", True
        return {**base, "status": status, "terminal": terminal, "r_multiple": None if r is None else round(r, 4), "tp1_reached": bool(tp1_seen), "mfe_r": mfe, "mae_r": mae, "settled_through_ms": end, "market_source": "BYBIT_LINEAR_PUBLIC_5M_1M"}
    except Exception as e:
        return {**base, "status": "MARKET_DATA_ERROR", "terminal": False, "r_multiple": None, "error": str(e)[:500]}


def summarize(rows):
    terminal = [r for r in rows if r.get("terminal") and r.get("r_multiple") is not None]
    wins = [r for r in terminal if r["r_multiple"] > 0]
    losses = [r for r in terminal if r["r_multiple"] < 0]
    rs = [float(r["r_multiple"]) for r in terminal]
    pos = sum(x for x in rs if x > 0)
    neg = abs(sum(x for x in rs if x < 0))
    by_dir = {}
    for direction in ("LONG", "SHORT"):
        rr = [r for r in terminal if r.get("geometry", {}).get("direction") == direction]
        vals = [float(r["r_multiple"]) for r in rr]
        by_dir[direction] = {"n": len(vals), "net_r": round(sum(vals), 4), "avg_r": round(sum(vals)/len(vals), 4) if vals else None, "win_rate_pct": round(100*sum(x>0 for x in vals)/len(vals), 2) if vals else None}
    return {
        "episodes": len(rows), "terminal": len(terminal), "open_or_error": len(rows)-len(terminal),
        "wins": len(wins), "losses": len(losses), "win_rate_pct": round(100*len(wins)/len(terminal), 2) if terminal else None,
        "net_r": round(sum(rs), 4), "average_r": round(sum(rs)/len(rs), 4) if rs else None,
        "profit_factor_r": round(pos/neg, 4) if neg > 0 else None,
        "by_direction": by_dir,
        "market_data_errors": sum(r.get("status") == "MARKET_DATA_ERROR" for r in rows),
        "ambiguous": sum(r.get("status") == "AMBIGUOUS" for r in rows),
    }


def main():
    snapshots = load_snapshots()
    episodes = build_episodes(snapshots)
    now = int(time.time() * 1000)
    matured = [e for e in episodes if now >= e["captured_at_ms"] + HORIZON_H * 3600_000]
    # Bound each run; newest episodes remain represented and old ones can be recomputed deterministically.
    rows = []
    for i, ep in enumerate(matured[-120:]):
        rows.append(settle(ep, now))
        if i and i % 12 == 0:
            time.sleep(0.3)
    report = {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "horizon_hours": HORIZON_H,
        "source_history": str(HISTORY.relative_to(ROOT)),
        "episode_semantics": "FIRST_QUALIFIED_OBSERVATION_PER_CONTIGUOUS_SYMBOL_DIRECTION_EPISODE",
        "methodology": "Canonical Production entry/SL/TP2 frozen at episode start; first 5m touch, 1m refinement for same-5m ambiguity; expired positions marked to market at 12h.",
        "research_only": True,
        "live_execution": False,
        "can_override_production": False,
        "can_change_threshold": False,
        "production_threshold_unchanged": 68,
        "summary": summarize(rows),
        "records": rows,
    }
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(report, indent=2, sort_keys=True))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text("\n".join(json.dumps(r, separators=(",", ":"), sort_keys=True) for r in rows) + ("\n" if rows else ""))
    print(json.dumps({"schema": SCHEMA, "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
