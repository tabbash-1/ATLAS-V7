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
SCHEMA = "ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V2_PROVIDER_CHAIN"


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
    entry = fnum(plan.get("entry")); stop = fnum(plan.get("stop_loss")); tp1 = fnum(plan.get("tp1")); tp2 = fnum(plan.get("tp2"))
    rr1 = fnum(plan.get("rr_tp1")); rr2 = fnum(plan.get("rr_tp2"))
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
    return {"direction": direction, "entry": entry, "stop_loss": stop, "tp1": tp1, "tp2": tp2,
            "rr_tp1": rr1, "rr_tp2": rr2, "risk_abs": risk,
            "trade_plan_version": plan.get("version"), "entry_mode": plan.get("entry_mode")}


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
            if current and current.get("direction") == g["direction"]:
                continue
            captured = t.isoformat()
            ep = {"id": episode_id(symbol, captured, g), "symbol": symbol, "captured_at": captured,
                  "captured_at_ms": int(t.timestamp() * 1000), "score": fnum(d.get("score")),
                  "threshold": fnum(d.get("signal_threshold")), "playbook": d.get("playbook"),
                  "regime": d.get("regime"), "execution_ready_at_capture": bool(d.get("execution_ready")),
                  "geometry": g}
            episodes.append(ep)
            active[symbol] = {"direction": g["direction"], "id": ep["id"]}
    return episodes


def request_json(url: str, timeout=20, body: bytes | None = None):
    headers = {"User-Agent": "ATLAS-Offline-Settlement/2.0", "Accept": "application/json", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def binance_klines(symbol: str, interval: str, start_ms: int, end_ms: int):
    if symbol == "HYPEUSDT":
        raise RuntimeError("HYPE_NOT_ON_BINANCE_SPOT_CHAIN")
    q = urllib.parse.urlencode({"symbol": symbol, "interval": interval + "m", "startTime": start_ms, "endTime": end_ms, "limit": 1000})
    raw = request_json("https://data-api.binance.vision/api/v3/klines?" + q)
    if not isinstance(raw, list):
        raise RuntimeError("invalid_binance_response")
    out = []
    for k in raw:
        try: out.append({"open_time": int(k[0]), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])})
        except Exception: pass
    return sorted(out, key=lambda x: x["open_time"])


def cryptocompare_minutes(symbol: str, start_ms: int, end_ms: int):
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    span_min = max(1, int(math.ceil((end_ms - start_ms) / 60000)))
    limit = min(2000, span_min + 5)
    q = urllib.parse.urlencode({"fsym": base, "tsym": "USDT", "limit": limit, "toTs": int(end_ms / 1000)})
    raw = request_json("https://min-api.cryptocompare.com/data/v2/histominute?" + q)
    rows = (((raw or {}).get("Data") or {}).get("Data") or [])
    out = []
    for k in rows:
        try:
            ms = int(k["time"]) * 1000
            if start_ms <= ms <= end_ms:
                out.append({"open_time": ms, "open": float(k["open"]), "high": float(k["high"]), "low": float(k["low"]), "close": float(k["close"])})
        except Exception:
            pass
    return sorted(out, key=lambda x: x["open_time"])


def aggregate_minutes(rows, minutes: int):
    if minutes <= 1:
        return rows
    buckets = {}
    width = minutes * 60_000
    for r in rows:
        key = (int(r["open_time"]) // width) * width
        b = buckets.setdefault(key, {"open_time": key, "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"]})
        b["high"] = max(b["high"], r["high"]); b["low"] = min(b["low"], r["low"]); b["close"] = r["close"]
    return [buckets[k] for k in sorted(buckets)]


def hyperliquid_klines(symbol: str, interval: str, start_ms: int, end_ms: int):
    if symbol != "HYPEUSDT":
        raise RuntimeError("HYPERLIQUID_ONLY_FOR_HYPE")
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": "HYPE", "interval": interval + "m", "startTime": start_ms, "endTime": end_ms}}).encode()
    raw = request_json("https://api.hyperliquid.xyz/info", body=body)
    if not isinstance(raw, list):
        raise RuntimeError("invalid_hyperliquid_response")
    out = []
    for k in raw:
        try: out.append({"open_time": int(k.get("t")), "open": float(k.get("o")), "high": float(k.get("h")), "low": float(k.get("l")), "close": float(k.get("c"))})
        except Exception: pass
    return sorted(out, key=lambda x: x["open_time"])


def market_klines(symbol: str, interval: str, start_ms: int, end_ms: int):
    errors = []
    try:
        rows = binance_klines(symbol, interval, start_ms, end_ms)
        if rows: return rows, "BINANCE_DATA_API_SPOT"
    except Exception as e:
        errors.append("binance=" + str(e))
    if symbol == "HYPEUSDT":
        try:
            rows = hyperliquid_klines(symbol, interval, start_ms, end_ms)
            if rows: return rows, "HYPERLIQUID_PUBLIC"
        except Exception as e:
            errors.append("hyperliquid=" + str(e))
    try:
        mins = cryptocompare_minutes(symbol, start_ms, end_ms)
        rows = aggregate_minutes(mins, int(interval))
        if rows: return rows, "CRYPTOCOMPARE_AGGREGATE_MINUTE"
    except Exception as e:
        errors.append("cryptocompare=" + str(e))
    raise RuntimeError("all_market_providers_failed: " + " | ".join(errors))


def touches(c, p):
    return c["low"] <= p <= c["high"]


def event_from(candles, g):
    tp1_seen = False
    for c in candles:
        sl, tp1, tp2 = touches(c, g["stop_loss"]), touches(c, g["tp1"]), touches(c, g["tp2"])
        if sl and (tp1 or tp2): return "AMBIGUOUS", c, tp1_seen
        if sl: return "SL", c, tp1_seen
        if tp2: return "TP2", c, True
        if tp1: tp1_seen = True
    return ("TP1_ONLY" if tp1_seen else "NONE"), None, tp1_seen


def excursions(candles, g):
    if not candles: return None, None
    entry, risk, direction = g["entry"], g["risk_abs"], g["direction"]
    highs, lows = [c["high"] for c in candles], [c["low"] for c in candles]
    if direction == "LONG": mfe, mae = (max(highs)-entry)/risk, (entry-min(lows))/risk
    else: mfe, mae = (entry-min(lows))/risk, (max(highs)-entry)/risk
    return round(mfe, 4), round(mae, 4)


def settle(ep, now_ms):
    start = int(ep["captured_at_ms"]); maturity = start + HORIZON_H * 3600_000
    base = {**ep, "schema": SCHEMA, "research_only": True, "live_execution": False, "can_override_production": False}
    if now_ms < maturity:
        return {**base, "status": "OPEN", "terminal": False, "r_multiple": None}
    end = maturity
    try:
        candles, provider = market_klines(ep["symbol"], "5", start, end)
        if not candles:
            raise RuntimeError("no_5m_candles")
        ev, candle, tp1_seen = event_from(candles, ep["geometry"])
        if ev == "AMBIGUOUS" and candle:
            one, provider_1m = market_klines(ep["symbol"], "1", candle["open_time"], candle["open_time"] + 5*60_000 - 1)
            ev1, _, tp1_before_1m = event_from(one, ep["geometry"])
            ev = ev1 if ev1 in {"SL", "TP2"} else "AMBIGUOUS"
            tp1_seen = tp1_seen or tp1_before_1m
            provider = provider + "+1M:" + provider_1m
        mfe, mae = excursions(candles, ep["geometry"])
        if ev == "SL": status, r, terminal = "LOSS", -1.0, True
        elif ev == "TP2": status, r, terminal = "WIN_TP2", float(ep["geometry"]["rr_tp2"]), True
        elif ev == "AMBIGUOUS": status, r, terminal = "AMBIGUOUS", None, False
        else:
            last = candles[-1]["close"]; g = ep["geometry"]
            directional = (last-g["entry"]) if g["direction"] == "LONG" else (g["entry"]-last)
            r = directional / g["risk_abs"]
            status, terminal = ("EXPIRED_TP1" if tp1_seen else "EXPIRED"), True
        return {**base, "status": status, "terminal": terminal, "r_multiple": None if r is None else round(r,4),
                "tp1_reached": bool(tp1_seen), "mfe_r": mfe, "mae_r": mae, "settled_through_ms": end,
                "market_source": provider}
    except Exception as e:
        return {**base, "status": "MARKET_DATA_ERROR", "terminal": False, "r_multiple": None, "error": str(e)[:700]}


def summarize(rows):
    terminal = [r for r in rows if r.get("terminal") and r.get("r_multiple") is not None]
    rs = [float(r["r_multiple"]) for r in terminal]
    wins, losses = [x for x in rs if x > 0], [x for x in rs if x < 0]
    pos, neg = sum(wins), abs(sum(losses))
    by_dir = {}
    for direction in ("LONG", "SHORT"):
        vals = [float(r["r_multiple"]) for r in terminal if r.get("geometry",{}).get("direction") == direction]
        by_dir[direction] = {"n":len(vals), "net_r":round(sum(vals),4), "avg_r":round(sum(vals)/len(vals),4) if vals else None,
                             "win_rate_pct":round(100*sum(x>0 for x in vals)/len(vals),2) if vals else None}
    providers = {}
    for r in rows:
        if r.get("market_source"): providers[r["market_source"]] = providers.get(r["market_source"],0)+1
    return {"episodes":len(rows), "terminal":len(terminal), "open_or_error":len(rows)-len(terminal),
            "wins":len(wins), "losses":len(losses), "win_rate_pct":round(100*len(wins)/len(terminal),2) if terminal else None,
            "net_r":round(sum(rs),4), "average_r":round(sum(rs)/len(rs),4) if rs else None,
            "profit_factor_r":round(pos/neg,4) if neg>0 else None, "by_direction":by_dir,
            "market_data_errors":sum(r.get("status")=="MARKET_DATA_ERROR" for r in rows),
            "ambiguous":sum(r.get("status")=="AMBIGUOUS" for r in rows), "provider_counts":providers}


def main():
    episodes = build_episodes(load_snapshots()); now = int(time.time()*1000)
    matured = [e for e in episodes if now >= e["captured_at_ms"] + HORIZON_H*3600_000]
    rows = []
    for i, ep in enumerate(matured[-120:]):
        rows.append(settle(ep, now))
        if i and i % 12 == 0: time.sleep(0.3)
    report = {"schema":SCHEMA, "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(), "horizon_hours":HORIZON_H,
              "source_history":str(HISTORY.relative_to(ROOT)),
              "episode_semantics":"FIRST_QUALIFIED_OBSERVATION_PER_CONTIGUOUS_SYMBOL_DIRECTION_EPISODE",
              "methodology":"Canonical Production entry/SL/TP2 frozen at episode start; public provider chain; first 5m touch, 1m refinement for same-5m ambiguity; expired positions marked to market at 12h.",
              "research_only":True, "live_execution":False, "can_override_production":False, "can_change_threshold":False,
              "production_threshold_unchanged":68, "summary":summarize(rows), "records":rows}
    LATEST.parent.mkdir(parents=True, exist_ok=True); LATEST.write_text(json.dumps(report,indent=2,sort_keys=True))
    LEDGER.parent.mkdir(parents=True, exist_ok=True); LEDGER.write_text("\n".join(json.dumps(r,separators=(",",":"),sort_keys=True) for r in rows) + ("\n" if rows else ""))
    print(json.dumps({"schema":SCHEMA,"summary":report["summary"]},indent=2))

if __name__ == "__main__": main()
