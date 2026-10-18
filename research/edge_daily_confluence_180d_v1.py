#!/usr/bin/env python3
"""ATLAS 1D context vs 4-12h direction: research-only historical audit.

Compares fixed Edge V1 paired first-hit trade paths across DAILY_ALIGNED,
DAILY_COUNTER and DAILY_NEUTRAL observations. 1D metrics are computed
exclusively from complete UTC calendar days already closed at observation.
Retains a chronological holdout and checks all three 12h spaced phases.

No model fitting/selection, no Production or Final Trade Gate mutation,
no live trading, no claim of prospective or executable profit.
"""
from __future__ import annotations

import argparse
import bisect
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from rc10_1_deep_analysis_overlay import daily_macro_context
from research.edge_event_ledger_v1 import HOUR_MS, HORIZON_H, build_ledger
from research.edge_real_market_baselines_v1 import (
    POLICIES, _policy_direction, asof_last_closed_hour, fetch_completed_1h
)
from research.edge_real_market_regime_audit_v1 import SYMBOLS

SCHEMA = "ATLAS_EDGE_1D_CONFLUENCE_180D_AUDIT_V1"
DAY_MS = 24 * HOUR_MS
DAYS = 180
COST_BPS = 17.0
MIN_COMPLETED_DAYS = 60
PURGE_H = 24
SEGMENTS = ("DAILY_ALIGNED", "DAILY_COUNTER", "DAILY_NEUTRAL")
PHASES = (0, 1, 2)


def completed_daily_from_hourly(hourly):
    """Produce UTC daily bars only when all 24 completed hours are present.

    Input timeline strictly contiguous/validated upstream; never include
    incomplete start/end-day bars, and retain true UTC day close_time.
    """
    by_day = defaultdict(list)
    for hour in hourly:
        t = int(hour["time"])
        if t % HOUR_MS:
            raise ValueError("1h source not UTC-aligned")
        if int(hour["close_time"]) != t + HOUR_MS - 1:
            raise ValueError("Invalid hourly close-time convention")
        by_day[t // DAY_MS].append(hour)
    result = []
    for day in sorted(by_day):
        rows = by_day[day]
        day_open = day * DAY_MS
        if len(rows) != 24:
            continue
        if any(row["time"] != day_open + i * HOUR_MS for i, row in enumerate(rows)):
            raise ValueError("Incomplete UTC daily timeline")
        result.append({
            "open_time": day_open,
            "close_time": day_open + DAY_MS - 1,
            "open": rows[0]["open"], "close": rows[-1]["close"],
            "high": max(r["high"] for r in rows),
            "low": min(r["low"] for r in rows),
            "volume": sum(r["volume"] for r in rows),
        })
    return result


def daily_by_observation(market, timestamps):
    """Compute one frozen daily state per *completed* day, never future data."""
    daily = completed_daily_from_hourly(market)
    finishes = [row["close_time"] for row in daily]
    cache = {}
    mapped = {}
    for at in sorted(set(timestamps)):
        n = bisect.bisect_right(finishes, at)
        if n < MIN_COMPLETED_DAYS:
            mapped[at] = None
            continue
        if n not in cache:
            state = daily_macro_context(daily[:n], direction=None)
            if state["status"] != "READY":
                raise ValueError("Daily source insufficient despite ready count")
            cache[n] = state
        frozen = cache[n]
        if frozen["last_closed_day_end_ms"] > at:
            raise ValueError("FUTURE_DAILY_CANDLE_LEAK")
        mapped[at] = frozen
    return mapped, {
        "daily_bars": len(daily),
        "first_closed_utc": datetime.fromtimestamp(finishes[0]/1000, timezone.utc).isoformat()
            if finishes else None,
        "last_closed_utc": datetime.fromtimestamp(finishes[-1]/1000, timezone.utc).isoformat()
            if finishes else None,
        "no_incomplete_daily_candle": True,
    }


def aligned_segment(daily_context, direction):
    if daily_context is None:
        return "DAILY_HISTORY_UNAVAILABLE"
    if direction not in ("LONG", "SHORT"):
        raise ValueError("No settled direction")
    bias = daily_context["bias"]
    if bias == "NEUTRAL":
        return "DAILY_NEUTRAL"
    return "DAILY_ALIGNED" if bias == direction else "DAILY_COUNTER"


def _stats(rows):
    """Modelled 17bp after-cost R on identical frozen Edge trade paths."""
    net = [r["settlement"]["modeled_net_r"] for r in rows
           if r["settlement"]["modeled_net_r"] is not None]
    gross = [r["settlement"]["gross_r"] for r in rows
             if r["settlement"]["gross_r"] is not None]
    pos = [v for v in net if v > 0]
    neg = [v for v in net if v < 0]
    return {
        "selected": len(rows), "settled": len(net),
        "excluded_ambiguous_or_unexecutable": len(rows)-len(net),
        "mean_gross_r": round(sum(gross)/len(gross), 5) if gross else None,
        "mean_modelled_net_r": round(sum(net)/len(net), 5) if net else None,
        "positive_net_pct": round(100*len(pos)/len(net), 2) if net else None,
        "modelled_profit_factor": round(sum(pos)/abs(sum(neg)), 4) if neg else None,
        "independent_observations_claim": False,
    }


def compare(ledgers, market_by_symbol, train_pct=70):
    """All 3 phases; discovery vs holdout, segment outcomes, fixed policies.

    Reject any daily context with a future closing time and any unmatched
    directional event; sample selection is never based on realized returns.
    """
    if not (60 <= train_pct <= 80):
        raise ValueError("Train percent out of research protocol")
    paired = defaultdict(dict)
    all_times = set()
    for ledger in ledgers:
        if ledger["schema"] != "ATLAS_EDGE_EVENT_LEDGER_V1":
            raise ValueError("Wrong Edge V1 path labels")
        symbol = ledger["symbol"]
        if symbol not in market_by_symbol:
            raise ValueError("Missing asset history")
        for row in ledger["rows"]:
            key = (symbol, row["event_at_ms"])
            if row["direction"] in paired[key]:
                raise ValueError("Repeated same-direction observation")
            paired[key][row["direction"]] = row
            all_times.add(row["event_at_ms"])
    if not paired:
        raise ValueError("No Edge direction-paired events")
    all_times = sorted(all_times)
    if len(all_times) < 90:
        raise ValueError("Insufficient market timeline")
    cut = all_times[int(len(all_times)*train_pct/100)]
    phase_base = all_times[0]
    timestamps_by_asset = defaultdict(set)
    for sym, at in paired:
        timestamps_by_asset[sym].add(at)
    daily_state, quality = {}, {}
    for sym in sorted(timestamps_by_asset):
        daily_state[sym], quality[sym] = daily_by_observation(
            market_by_symbol[sym], timestamps_by_asset[sym])
    buckets = {
        str(slot):{part:{p:defaultdict(list) for p in POLICIES}
                   for part in ("discovery","holdout")}
        for slot in PHASES
    }
    skipped_immature_daily = 0
    purged = 0
    for (sym, at), d in sorted(paired.items()):
        if set(d) != {"LONG","SHORT"}:
            raise ValueError("Broken paired-event contract")
        if d["LONG"]["features"] != d["SHORT"]["features"]:
            raise ValueError("Nonidentical causal features across directions")
        frozen = daily_state[sym][at]
        if frozen is None:
            skipped_immature_daily += 1
            continue
        if frozen["last_closed_day_end_ms"] > at:
            raise ValueError("Future daily evidence present")
        phase = (at-phase_base)//(4*HOUR_MS)
        if (at-phase_base)%(4*HOUR_MS) != 0:
            raise ValueError("Event timestamp not on common 4h grid")
        slot = str(phase%3)
        if d["LONG"]["forward_matures_at_ms"] < cut-PURGE_H*HOUR_MS:
            part="discovery"
        elif at >= cut:
            part="holdout"
        else:
            purged += 1
            continue
        f = d["LONG"]["features"]
        for policy in POLICIES:
            direction = _policy_direction(policy, f)
            if direction is None:
                continue
            chosen=d[direction]
            segment=aligned_segment(frozen,direction)
            lane=buckets[slot][part][policy]
            lane["ALL"].append(chosen)
            lane[segment].append(chosen)
    result = {}
    for slot, periods in buckets.items():
        result[slot] = {}
        for part, policies in periods.items():
            result[slot][part] = {
                p:{seg:_stats(groups.get(seg, [])) for seg in ("ALL",)+SEGMENTS}
                for p, groups in policies.items()
            }
    return {
        "split":{
            "cutoff_ms":cut,
            "cutoff_utc":datetime.fromtimestamp(cut/1000,timezone.utc).isoformat(),
            "train_pct":train_pct, "purge_h_before_holdout":PURGE_H,
            "daily_history_not_yet_mature_asset_events":skipped_immature_daily,
            "purged_asset_events":purged,
        },
        "daily_data_quality":quality,
        "all_three_12h_nonoverlap_phases":result,
        "all_phases_checked_before_promotion":True,
        "holdout_already_exposed_by_prior_90d_research":True,
        "policy_or_filter_selected_based_on_outcomes":False,
    }


def run(symbols=SYMBOLS, days=DAYS, as_of_ms=None,
        fetcher=fetch_completed_1h, cost_bps=COST_BPS):
    if days != DAYS:
        raise ValueError("Fixed preregistered comparison requires 180 days")
    if not symbols or len(set(symbols))!=len(symbols) or "BTCUSDT" not in symbols:
        raise ValueError("BTC-first unique research universe required")
    if cost_bps != COST_BPS:
        raise ValueError("Locked cost scenario must remain 17bps")
    as_of_ms = (asof_last_closed_hour(int(time.time()*1000))
                if as_of_ms is None else as_of_ms)
    source = {}
    meta = {}
    for sym in symbols:
        candles, quality = fetcher(sym,days,as_of_ms)
        if not quality["continuity_validated"] or len(candles) != days*24:
            raise ValueError("Bad source history: "+sym)
        if candles[-1]["close_time"] != as_of_ms:
            raise ValueError("Market as-of divergence: "+sym)
        source[sym] = candles
        meta[sym] = quality
    btc=source["BTCUSDT"]
    ledgers=[build_ledger(sym,source[sym],btc,as_of_ms,modeled_cost_bps=cost_bps)
             for sym in symbols]
    audit=compare(ledgers,source)
    return {
        "schema":SCHEMA,"as_of_ms":as_of_ms,
        "days":days,"symbols":list(symbols),"public_spot_market_data":meta,
        "daily_definition":"ONLY_24_COMPLETED_UTC_1H_CANDLES",
        "daily_bias_method":"EXISTING_RC10_DEEP_ANALYSIS_BIAS_2_OF_3_EMA20_EMA50_RSI14",
        "cost_bps_scenario":COST_BPS,
        "hypothetical_geometry":"NEXT_1H_OPEN_STOP_1P5ATR_TP_2P5R_12H_FIRST_TOUCH",
        **audit,
        "daily_filter_can_be_promoted":False,
        "profitability_validated":False,
        "prospective_evidence_available":False,
        "research_only":True,"can_create_trade":False,
        "can_change_production":False,"can_change_threshold":False,
        "can_override_final_trade_gate":False,
        "limitations":[
            "Historical market data were already examined in earlier Edge studies; holdout is NOT blind",
            "Event paths are theoretical next-hour-open entries rather than actual Atlas trades",
            "17bps is an unverified cost scenario (not real fee/spread/slippage/funding)",
            "Spot short labels assume counterfactual borrow and cannot be traded spot without it",
            "Shared BTC market shocks and 12h overlapping across alternative phases require caution",
            "Daily bias is a trend proxy, not calibrated predictive probability",
            "Outcome-conditioned filters and positive subgroup selections are not authorized",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--symbols",default=",".join(SYMBOLS))
    parser.add_argument("--days",default=DAYS,type=int)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    report=run(tuple(x.strip().upper() for x in args.symbols.split(",") if x.strip()),
               args.days)
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    compact={
        "schema":SCHEMA,"daily_history_unavailable":report["split"]["daily_history_not_yet_mature_asset_events"],
        "results":{
            slot:{p:{
                period:{segment:{
                    "n":report["all_three_12h_nonoverlap_phases"][slot][period][p][segment]["settled"],
                    "net_R":report["all_three_12h_nonoverlap_phases"][slot][period][p][segment]["mean_modelled_net_r"],
                } for segment in ("ALL",)+SEGMENTS}
                for period in ("discovery","holdout")
            } for p in POLICIES}
            for slot in ("0","1","2")
        },
        "profitability_validated":False,
    }
    print(json.dumps(compact,sort_keys=True))


if __name__=="__main__":
    main()
