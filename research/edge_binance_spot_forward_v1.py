#!/usr/bin/env python3
"""Binance spot venue-aware *prospective* Edge evidence (research only).

This is not a trading system: no private endpoints, keys, orders, or
Production imports. Capture stores immutable closed-bar features, public
bid/ask, and frozen hypothetical LONG/SHORT/WAIT plans. A later run
settles only after a full *future* 720 minute-bar path exists.

Quotes are sampled at runtime, never reconstructed for missed slots.
All policy decisions are predeclared and untouched by settled results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from research.edge_event_ledger_v1 import HOUR_MS, frozen_features
from research.edge_real_market_baselines_v1 import POLICIES, _policy_direction

VERSION = "ATLAS_EDGE_BINANCE_VENUE_FORWARD_V1"
LEDGER_SCHEMA = VERSION + "_LEDGER"
LATEST_SCHEMA = VERSION + "_LATEST"
ROOT = "https://data-api.binance.vision"
MINUTE_MS = 60_000
HORIZON_MIN = 720
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
CLOSED_BAR_MAX_AGE_MS = 20 * MINUTE_MS
QUOTE_MAX_AGE_MS = 60_000
MAX_SPREAD_BPS_OBSERVABLE = 75
MIN_HISTORY = 40
STOP_ATR = 1.5
TP_R = 2.5
ROUNDTRIP_FEE_BPS_SCENARIO = 11.0  # NOT a documented account fee
MAX_SETTLE_PER_RUN = 48
MIN_CAPTURE_SPACING_MS = 4 * HOUR_MS


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def digest(record):
    frozen = {k: v for k, v in record.items() if k != "capture_sha256"}
    return hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _finite(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Nonfinite venue value")
    return value


def _api(path, params, request_fn=None):
    """Only two public Binance SPOT read-only market endpoints."""
    if path not in ("/api/v3/ticker/bookTicker", "/api/v3/klines"):
        raise ValueError("Research only uses approved public spot market endpoints")
    request_fn = request_fn or urllib.request.urlopen
    url = ROOT + path + "?" + urllib.parse.urlencode(params)
    with request_fn(url, timeout=20) as response:
        payload = json.loads(response.read())
    if path == "/api/v3/klines":
        if not isinstance(payload, list):
            raise ValueError("Invalid spot kline response")
    elif not isinstance(payload, dict):
        raise ValueError("Invalid spot bookTicker response")
    return payload


def book_snapshot(symbol, now_ms, request_fn=None):
    data = _api("/api/v3/ticker/bookTicker", {"symbol": symbol}, request_fn)
    if data.get("symbol") != symbol:
        raise ValueError("Missing exact Binance spot symbol")
    bid = _finite(data["bidPrice"])
    ask = _finite(data["askPrice"])
    bid_size = _finite(data.get("bidQty", "0"))
    ask_size = _finite(data.get("askQty", "0"))
    if not (0 < bid < ask and bid_size > 0 and ask_size > 0):
        raise ValueError("Invalid spot bid ask or empty top of book")
    spread = 10_000 * (ask - bid) / ((ask + bid) / 2)
    if spread > MAX_SPREAD_BPS_OBSERVABLE:
        raise ValueError("Abnormal spread: fail closed")
    return {
        "market": "BINANCE_SPOT_USDT", "quote_at_ms": now_ms,
        "quote_timestamp_kind": "LOCAL_CAPTURE_CLOCK_NOT_EXCHANGE_TIMESTAMP",
        "bid": bid, "ask": ask, "bid_size": bid_size,
        "ask_size": ask_size, "spread_bps": round(spread, 6),
        "source": "PUBLIC_BINANCE_SPOT_TOP_OF_BOOK",
        "not_an_execution_fill": True,
    }


def market_candles(symbol, interval, now_ms, start_ms=None, end_ms=None, request_fn=None):
    if interval not in (1, 60) or symbol not in SYMBOLS:
        raise ValueError("Unsupported spot market candle query")
    params = {"symbol": symbol,
              "interval": "1m" if interval == 1 else "1h", "limit": 1000}
    if start_ms is not None:
        params["startTime"] = int(start_ms)
    if end_ms is not None:
        params["endTime"] = int(end_ms + interval * MINUTE_MS - 1)
    obj = _api("/api/v3/klines", params, request_fn)
    step = interval * MINUTE_MS
    candles = []
    for row in obj:
        if not isinstance(row, list) or len(row) < 7:
            raise ValueError("Malformed spot kline")
        t = int(row[0])
        a, high, low, close, volume = (_finite(z) for z in row[1:6])
        if not (t >= 0 and a > 0 and low > 0 and high >= max(a, close)
                and low <= min(a, close) and volume >= 0):
            raise ValueError("Invalid spot kline geometry")
        if t + step <= now_ms:
            candles.append({"time": t, "close_time": t + step - 1,
                            "open": a, "high": high, "low": low,
                            "close": close, "volume": volume})
    candles.sort(key=lambda k: k["time"])
    for prev, curr in zip(candles, candles[1:]):
        if curr["time"] - prev["time"] != step:
            raise ValueError("Duplicated/missing spot candles")
    if start_ms is not None and end_ms is not None:
        if not candles or candles[0]["time"] != start_ms or candles[-1]["time"] != end_ms:
            raise ValueError("Missing exact future spot path boundaries")
        expected = (end_ms - start_ms) // step + 1
        if len(candles) != expected:
            raise ValueError("Missing future path bars")
    elif len(candles) < MIN_HISTORY:
        raise ValueError("Insufficient previous closed spot history")
    return candles


def freeze(symbol, market, btc, book, now_ms):
    """Freeze latest actually-closed SPOT 1h context and public book quote.

    A schedule delay must never reconstruct a historical would-have-traded
    open; only actually-observed quote at the runtime may be considered.
    """
    if not market or not btc:
        raise ValueError("Missing closed BTC/asset history")
    last = market[-1]
    decision_at = int(last["close_time"]) + 1
    if not (0 <= now_ms - decision_at <= CLOSED_BAR_MAX_AGE_MS):
        raise ValueError("Missed capture window: no backfill")
    if book["quote_at_ms"] < decision_at or abs(book["quote_at_ms"] - now_ms) > QUOTE_MAX_AGE_MS:
        raise ValueError("Quote predates observed candle or stale")
    bi = {c["close_time"]: i for i, c in enumerate(btc)}.get(last["close_time"])
    if bi is None or bi < MIN_HISTORY or len(market) - 1 < MIN_HISTORY:
        raise ValueError("BTC and asset not aligned to latest closed hour")
    features = frozen_features(market, btc, len(market) - 1, bi)
    # Market feature computations MUST see only closed candles.
    if features["observed_close_time_ms"] >= book["quote_at_ms"]:
        raise ValueError("Future market features")
    atr = float(features["atr14"])
    if atr <= 0:
        raise ValueError("ATR zero")
    records = []
    for policy in POLICIES:
        side = _policy_direction(policy, features) or "WAIT"
        entry = book["ask"] if side == "LONG" else book["bid"] if side == "SHORT" else None
        stop = target = None
        if entry is not None:
            direction = 1 if side == "LONG" else -1
            stop = entry - direction * STOP_ATR * atr
            target = entry + direction * STOP_ATR * atr * TP_R
            if min(stop, target) <= 0:
                side, entry, stop, target = "WAIT", None, None, None
        # First *fully future* 1m candle; initial <60s unobserved
        # window is explicitly not considered executable outcome evidence.
        path_start = (book["quote_at_ms"] // MINUTE_MS + 1) * MINUTE_MS
        frozen = {
            "market": "BINANCE_SPOT_USDT",
            "short_spot_is_counterfactual_without_borrow": side == "SHORT",
            "quote_exchange_timestamp_unavailable": True,
            "id": hashlib.sha256(
                f"{VERSION}|{symbol}|{decision_at}|{policy}".encode()).hexdigest()[:24],
            "symbol": symbol, "policy": policy,
            "direction": side, "decision_at_ms": decision_at,
            "captured_at_ms": now_ms, "quote_at_ms": book["quote_at_ms"],
            "features": features, "book": book,
            "entry_side_quote": entry,
            "stop_loss": round(stop, 10) if stop is not None else None,
            "take_profit": round(target, 10) if target is not None else None,
            "stop_atr": STOP_ATR, "tp_target_r": TP_R,
            "settlement_window_start_ms": path_start,
            "settlement_window_end_ms": path_start + (HORIZON_MIN - 1) * MINUTE_MS,
            "initial_partial_minute_coverage": "UNOBSERVED_PROHIBITS_EXECUTION_CLAIM",
            "fee_roundtrip_bps_assumption": ROUNDTRIP_FEE_BPS_SCENARIO,
            "funding_measured": False, "exit_spread_measured": False,
            "research_only": True, "can_create_trade": False,
            "can_override_production": False, "can_override_final_trade_gate": False,
        }
        frozen["capture_sha256"] = digest(frozen)
        records.append(frozen)
    return records


def _settle(entry, bars):
    if entry["direction"] == "WAIT":
        return {"outcome": "WAIT", "gross_r": None, "modeled_net_r": None,
                "forward_outcome_not_a_trade": True}
    if len(bars) != HORIZON_MIN or bars[0]["time"] != entry["settlement_window_start_ms"]:
        raise ValueError("Invalid future minute-bar window")
    if bars[-1]["time"] != entry["settlement_window_end_ms"]:
        raise ValueError("Incomplete 12h settlement")
    risk = abs(entry["entry_side_quote"] - entry["stop_loss"])
    if risk <= 0:
        raise ValueError("Invalid frozen risk")
    direction = entry["direction"]
    target = entry["take_profit"]
    stop = entry["stop_loss"]
    if direction == "LONG":
        def values(bar):
            return bar["open"] <= stop, bar["open"] >= target, bar["low"] <= stop, bar["high"] >= target
        sign = 1
    else:
        def values(bar):
            return bar["open"] >= stop, bar["open"] <= target, bar["high"] >= stop, bar["low"] <= target
        sign = -1
    outcome = "EXPIRED_12H"
    raw_exit = bars[-1]["close"]
    for bar in bars:
        open_stop, open_tp, hit_stop, hit_tp = values(bar)
        if open_stop:
            outcome, raw_exit = "SL_FIRST", bar["open"]
        elif open_tp:
            outcome, raw_exit = "TP_FIRST", target
        elif hit_stop and hit_tp:
            return {"outcome": "AMBIGUOUS_1M_ORDER", "gross_r": None,
                    "modeled_net_r": None, "not_trade_execution": True}
        elif hit_stop:
            outcome, raw_exit = "SL_FIRST", stop
        elif hit_tp:
            outcome, raw_exit = "TP_FIRST", target
        if outcome != "EXPIRED_12H":
            break
    entry_price = entry["entry_side_quote"]
    gross_r = sign * (raw_exit - entry_price) / risk
    # Entry uses observed ask/bid; hypothetical exit spread uses *entry*
    # half spread (NO measured quote at future exit), and fees are a scenario.
    fee = entry_price * entry["fee_roundtrip_bps_assumption"] / 10_000
    exit_half_spread = raw_exit * entry["book"]["spread_bps"] / 20_000
    modeled_net_r = gross_r - (fee + exit_half_spread) / risk
    return {
        "outcome": outcome, "gross_r": round(gross_r, 6),
        "modeled_net_r": round(modeled_net_r, 6),
        "modelled_roundtrip_fee_bps": entry["fee_roundtrip_bps_assumption"],
        "estimated_exit_half_spread_bps": round(entry["book"]["spread_bps"] / 2, 6),
        "actual_fills_or_funding_measured": False,
        "first_full_minute_only_incomplete_immediate_path": True,
        "not_trade_execution": True,
    }


def _new_ledger():
    return {"schema": LEDGER_SCHEMA, "observations": [], "outcomes": {},
            "research_only": True, "can_create_trade": False,
            "can_override_production": False,
            "can_override_final_trade_gate": False,
            "profitability_validated": False}


def load(path):
    p = Path(path)
    doc = json.loads(p.read_text()) if p.exists() else _new_ledger()
    if doc.get("schema") != LEDGER_SCHEMA or not isinstance(doc.get("observations"), list) \
            or not isinstance(doc.get("outcomes"), dict):
        raise ValueError("Corrupt research ledger")
    keys = set()
    for row in doc["observations"]:
        if row["id"] in keys or row.get("capture_sha256") != digest(row):
            raise ValueError("Frozen observation mutated or duplicated")
        keys.add(row["id"])
    if not set(doc["outcomes"]).issubset(keys):
        raise ValueError("Orphan outcome")
    return doc


def write_atomic(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".research.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    os.replace(tmp, p)


def run(now_ms=None, request_fn=None,
        ledger_path="status/edge-binance-spot-forward-ledger.json",
        latest_path="status/edge-binance-spot-forward-latest.json"):
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    ledger = load(ledger_path)
    known = {x["id"] for x in ledger["observations"]}
    new_ids = []
    errors = {}
    btc = None
    # Fail-closed for BTC-first. No brand new cohort if BTC missing/stale.
    try:
        btc = market_candles("BTCUSDT", 60, now_ms, request_fn=request_fn)
        if not (0 <= now_ms - (btc[-1]["close_time"] + 1) <= CLOSED_BAR_MAX_AGE_MS):
            raise ValueError("Latest BTC hour not fresh")
    except Exception as exc:
        errors["BTC_CONTEXT"] = type(exc).__name__ + ": " + str(exc)

    if btc is not None:
        for sym in SYMBOLS:
            try:
                bars = btc if sym == "BTCUSDT" else market_candles(
                    sym, 60, now_ms, request_fn=request_fn)
                if bars[-1]["close_time"] != btc[-1]["close_time"]:
                    raise ValueError("Asset/BTC timestamp mismatch")
                previous = max((x["decision_at_ms"] for x in ledger["observations"]
                                if x["symbol"] == sym), default=None)
                decision_at = bars[-1]["close_time"] + 1
                if previous is not None and decision_at - previous < MIN_CAPTURE_SPACING_MS:
                    continue  # Hourly scheduler with minimum 4h capture spacing.
                book = book_snapshot(sym, now_ms, request_fn)
                frozen = freeze(sym, bars, btc, book, now_ms)
                for row in frozen:
                    if row["id"] in known:
                        # We do not overwrite a historical snapshot based on
                        # current quote. Re-running is idempotent.
                        continue
                    ledger["observations"].append(row)
                    known.add(row["id"])
                    new_ids.append(row["id"])
            except Exception as exc:
                errors[sym] = type(exc).__name__ + ": " + str(exc)

    # Settlement is separate: only after the *entire* future 12h interval
    # matured. One public Binance 1m fetch per shared symbol/timestamp window.
    cache = {}
    settled = []
    for row in ledger["observations"]:
        if len(settled) >= MAX_SETTLE_PER_RUN:
            break
        oid = row["id"]
        if oid in ledger["outcomes"]:
            continue
        if row["direction"] == "WAIT":
            ledger["outcomes"][oid] = {"outcome": "WAIT", "not_trade_execution": True}
            continue
        start, last = row["settlement_window_start_ms"], row["settlement_window_end_ms"]
        if now_ms < last + MINUTE_MS:
            continue
        key = (row["symbol"], start, last)
        try:
            if key not in cache:
                cache[key] = market_candles(
                    row["symbol"], 1, now_ms, start_ms=start, end_ms=last,
                    request_fn=request_fn)
            ledger["outcomes"][oid] = _settle(row, cache[key])
            settled.append(oid)
        except Exception as exc:
            errors["SETTLE_" + oid] = type(exc).__name__ + ": " + str(exc)
    ledger["checked_at_ms"] = now_ms
    write_atomic(ledger_path, ledger)

    settled_rows = [(x, ledger["outcomes"].get(x["id"]))
                    for x in ledger["observations"]]
    directional = [(x, o) for x, o in settled_rows
                   if o and x["direction"] != "WAIT"
                   and o.get("modeled_net_r") is not None]
    pending = sum(x["direction"] != "WAIT" and x["id"] not in ledger["outcomes"]
                  for x in ledger["observations"])
    latest = {
        "schema": LATEST_SCHEMA, "checked_at_ms": now_ms,
        "observations": len(ledger["observations"]),
        "new_observation_ids": new_ids, "new_settlement_ids": settled,
        "settled_directional_count": len(directional),
        "pending_directional": pending,
        "mean_modeled_net_r_descriptive": round(
            sum(o["modeled_net_r"] for _, o in directional) / len(directional), 6)
            if directional else None,
        "preselected_policies": list(POLICIES), "symbols": list(SYMBOLS),
        "errors": errors,
        "no_new_capture_when_quote_stale_or_missing": True,
        "profitability_validated": False,
        "venue": "BINANCE_SPOT_USDT",
        "quote_has_no_exchange_timestamp": True,
        "spot_shorts_nonexecutable_without_borrow": True,
        "live_execution": False, "research_only": True,
        "can_create_trade": False, "can_override_production": False,
        "can_override_final_trade_gate": False,
        "interpretation": "FROZEN_PROSPECTIVE_RESEARCH_ONLY_NO_PRODUCTION_PROMOTION",
    }
    write_atomic(latest_path, latest)
    return latest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="status/edge-binance-venue-forward-ledger.json")
    parser.add_argument("--latest", default="status/edge-binance-venue-forward-latest.json")
    args = parser.parse_args()
    print(json.dumps(run(ledger_path=args.ledger, latest_path=args.latest),
                     sort_keys=True))


if __name__ == "__main__":
    main()
