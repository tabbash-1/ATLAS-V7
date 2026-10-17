#!/usr/bin/env python3
"""Offline-safe real-market OHLCV retrieval + fixed-rule Edge V1 baseline comparison.

No exchange credentials, no trade routing, no Production import or mutation.
Network access is strictly public Binance SPOT 1H history; missing data fails
closed. A historical descriptive benchmark is not validated profitability.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research.edge_event_ledger_v1 import HOUR_MS, HORIZON_H, build_ledger, normalize_candles

VERSION = "ATLAS_EDGE_REAL_MARKET_BASELINES_V1"
HOSTS = ("https://data-api.binance.vision", "https://api-gcp.binance.com",
         "https://api1.binance.com", "https://api.binance.com")
RESEARCH_UNIVERSE = frozenset(("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "ZECUSDT", "ADAUSDT", "LINKUSDT",
    "AVAXUSDT", "LTCUSDT"))
MAX_BARS_PER_CALL = 1000
MIN_DAYS = 15
MAX_DAYS = 180


def asof_last_closed_hour(now_ms):
    """Last completed hourly UTC candle close (Binance exclusive-open scheme)."""
    return now_ms // HOUR_MS * HOUR_MS - 1


def fetch_completed_1h(symbol, days, as_of_ms, request_fn=None, hosts=HOSTS):
    """Fetch exactly days*24 closed contiguous 1H bars, checking every page."""
    if symbol not in RESEARCH_UNIVERSE:
        raise ValueError("Unsupported Binance spot research asset")
    if not (MIN_DAYS <= days <= MAX_DAYS):
        raise ValueError("days out of research bounds")
    if not hosts:
        raise ValueError("No public data provider")
    if (as_of_ms + 1) % HOUR_MS:
        raise ValueError("as_of must be last closed 1H UTC candle")
    request_fn = request_fn or urllib.request.urlopen
    end_time = as_of_ms
    start_time = as_of_ms + 1 - days * 24 * HOUR_MS
    cursor = start_time
    observed = []
    providers = []
    while cursor <= end_time:
        page_limit = min(MAX_BARS_PER_CALL, (end_time - cursor + 1) // HOUR_MS)
        if page_limit < 1:
            raise ValueError("Unaligned data page")
        query = urllib.parse.urlencode({
            "symbol":symbol, "interval":"1h", "startTime":cursor,
            "endTime":end_time, "limit":page_limit})
        data = None
        failures = []
        for host in hosts:
            try:
                with request_fn(host + "/api/v3/klines?" + query, timeout=18) as response:
                    raw = response.read()
                payload = json.loads(raw)
                if not isinstance(payload, list) or not payload:
                    raise ValueError("Empty or invalid Binance candles")
                data = payload
                providers.append(host)
                break
            except (urllib.error.HTTPError, urllib.error.URLError, OSError,
                    TimeoutError, ValueError, json.JSONDecodeError) as exc:
                failures.append(f"{host}: {type(exc).__name__}")
        if data is None:
            raise RuntimeError("Market data unavailable; no research sample: " + "; ".join(failures))
        batch = []
        for row in data:
            if not isinstance(row, list) or len(row) < 7:
                raise ValueError("Malformed Binance row")
            bar = {"time":int(row[0]), "open":float(row[1]), "high":float(row[2]),
                   "low":float(row[3]), "close":float(row[4]), "volume":float(row[5]),
                   "close_time":int(row[6])}
            batch.append(bar)
        if batch[0]["time"] != cursor:
            raise ValueError("Missing start or data hole; refusing to interpolate")
        if len(batch) > page_limit:
            raise ValueError("Provider exceeded requested page size")
        # Validate *each* returned page before appending to prevent silent gaps.
        norm = normalize_candles(batch, end_time)
        if len(norm) != len(batch):
            raise ValueError("Provider included incomplete or out-of-bound candle")
        observed.extend(norm)
        cursor = norm[-1]["time"] + HOUR_MS
        if cursor <= observed[-1]["time"]:
            raise ValueError("Non-progressing Binance pagination")
    expected = days * 24
    if len(observed) != expected:
        raise ValueError(f"Truncated real-market candles: got {len(observed)}, expected {expected}")
    normalize_candles(observed, end_time)
    return observed, {"symbol":symbol, "bars":len(observed),
                      "first_open_ms":observed[0]["time"],
                      "last_close_ms":observed[-1]["close_time"],
                      "data_providers_used":sorted(set(providers)),
                      "calendar_coverage_pct":100.0, "continuity_validated":True}


def _policy_direction(name, f):
    momentum = f["asset_return_4h_pct"]
    btc_mom = f["btc_return_4h_pct"]
    if name == "MOMENTUM_4H":
        signal = momentum
    elif name == "REVERSAL_4H":
        signal = -momentum
    elif name == "BTC_ALIGNED_4H":
        if not momentum * btc_mom > 0:
            return None
        signal = momentum
    elif name == "HTF_ALIGNED_12H":
        if not f["asset_return_12h_pct"] * f["btc_return_12h_pct"] > 0:
            return None
        signal = f["asset_return_12h_pct"]
    else:
        raise ValueError("Unknown preregistered baseline")
    return "LONG" if signal > 0 else "SHORT" if signal < 0 else None


POLICIES = ("MOMENTUM_4H", "REVERSAL_4H", "BTC_ALIGNED_4H", "HTF_ALIGNED_12H")


def _score(rows):
    unambiguous = [r for r in rows if r["settlement"]["gross_r"] is not None]
    gross = [r["settlement"]["gross_r"] for r in unambiguous]
    net = [r["settlement"]["modeled_net_r"] for r in unambiguous
           if r["settlement"]["modeled_net_r"] is not None]
    return {
        "selected":len(rows), "unambiguous":len(unambiguous),
        "ambiguous_or_unexecutable":len(rows)-len(unambiguous),
        "positive":sum(x > 0 for x in gross),
        "negative":sum(x < 0 for x in gross),
        "flat":sum(x == 0 for x in gross),
        "gross_mean_r_descriptive":round(sum(gross)/len(gross),5) if gross else None,
        "modeled_net_mean_r_descriptive":round(sum(net)/len(net),5) if net else None,
        "positive_rate_pct":round(100*sum(x > 0 for x in gross)/len(gross),2) if gross else None,
        "historical_independence_claim":False,
    }


def compare_baselines(ledgers, train_ratio=0.70):
    """Preregistered simple baselines, purged chronological split.

    Each 4h observation has a 12h label and *both* hypothetical directions.
    Train and holdout are split across timestamps, with a 12h purge boundary.
    Holdout does not select a winning model, and no numbers imply future edge.
    """
    if not 0.5 <= train_ratio <= 0.8:
        raise ValueError("Train split must be between 50% and 80%")
    events = defaultdict(dict)
    for ledger in ledgers:
        if ledger.get("schema") != "ATLAS_EDGE_EVENT_LEDGER_V1":
            raise ValueError("Incorrect event ledger schema")
        for row in ledger["rows"]:
            key=(row["symbol"], row["event_at_ms"])
            if row["direction"] in events[key]:
                raise ValueError("Duplicate same-event directional observation")
            events[key][row["direction"]] = row
    events = {k:v for k,v in events.items() if set(v)=={"LONG","SHORT"}}
    timestamps = sorted(set(t for (_,t) in events))
    if len(timestamps) < 10:
        raise ValueError("Insufficient observation dates to split")
    cutoff = timestamps[int(len(timestamps) * train_ratio)]
    selected = {"discovery":{name:[] for name in POLICIES},
                "holdout":{name:[] for name in POLICIES}}
    periods = {"discovery":set(), "holdout":set()}
    purged = 0
    for (_,t), pair in sorted(events.items()):
        mature = pair["LONG"]["forward_matures_at_ms"]
        if mature < cutoff - HORIZON_H * HOUR_MS:
            period = "discovery"
        elif t >= cutoff:
            period = "holdout"
        else:
            purged += 1
            continue
        periods[period].add(t)
        f = pair["LONG"]["features"]
        for name in POLICIES:
            direction=_policy_direction(name,f)
            if direction:
                selected[period][name].append(pair[direction])
    return {
        "method":"CHRONOLOGICAL_70_30_WITH_12H_PURGE_NO_FITTING",
        "cutoff_ms":cutoff, "cutoff_utc":datetime.fromtimestamp(cutoff/1000, timezone.utc).isoformat(),
        "purged_asset_time_events":purged,
        "overlapping_labels_and_common_btc_exposure":True,
        "scores":{period:{name:_score(rows) for name,rows in v.items()} for period,v in selected.items()},
        "unique_timestamp_counts":{p:len(times) for p,times in periods.items()},
        "winner_selected_from_holdout":False,
        "predictive_probabilities_calibrated":False,
        "net_production_pnl_claim":False,
    }


def run_real_benchmark(symbols, days, as_of_ms, modeled_cost_bps):
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError("No symbols or duplicate symbols")
    if modeled_cost_bps is not None and (modeled_cost_bps < 0 or modeled_cost_bps > 100):
        raise ValueError("Invalid cost scenario")
    if "BTCUSDT" not in symbols:
        symbols=["BTCUSDT"] + symbols
    if len(symbols) > 12:
        raise ValueError("Excessive research universe")
    btc,btc_quality=fetch_completed_1h("BTCUSDT",days,as_of_ms)
    ledgers, qualities = [], [btc_quality]
    for symbol in symbols:
        if symbol == "BTCUSDT":
            market = btc
        else:
            market,q=fetch_completed_1h(symbol,days,as_of_ms)
            qualities.append(q)
        ledgers.append(build_ledger(symbol,market,btc,as_of_ms,modeled_cost_bps))
    report = compare_baselines(ledgers)
    report.update({
        "schema":VERSION, "as_of_ms":as_of_ms, "days":days,
        "symbols":symbols, "market_data_quality":qualities,
        "hypothetical_research_only":True,
        "research_only":True, "live_execution":False, "can_create_trade":False,
        "can_override_production":False, "profitability_validated":False,
        "costs_are_unverified_scenarios":True, "modeled_roundtrip_cost_bps":modeled_cost_bps,
        "caveats":[
            "Baseline observations overlap; rows and assets are not independent",
            "Train/holdout dates separate labels but do not imply an untouched market regime",
            "Gross and modeled returns are hypothetical; no venue or paper ledger executions",
            "The tested fixed rules do not prove a profitable Production decision",
            "Historical discovery and holdout are descriptive, not prospective forward observations",
            "Do not select a winning strategy by comparing same holdout repeatedly",
        ],
    })
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--symbols",default="BTCUSDT,ETHUSDT,SOLUSDT")
    p.add_argument("--days",default=30,type=int)
    p.add_argument("--modeled-cost-bps",default=17.0,type=float)
    p.add_argument("--output",default="/tmp/atlas-edge-real-market-baselines.json")
    args=p.parse_args()
    symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    as_of=asof_last_closed_hour(int(time.time()*1000))
    report=run_real_benchmark(symbols,args.days,as_of,args.modeled_cost_bps)
    path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:report[k] for k in (
        "schema","as_of_ms","days","symbols","market_data_quality","scores",
        "profitability_validated")},sort_keys=True))


if __name__=="__main__":
    main()
