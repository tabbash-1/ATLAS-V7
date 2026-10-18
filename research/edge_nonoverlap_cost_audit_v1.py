#!/usr/bin/env python3
"""ATLAS research-only: nonoverlapping 12h, cross-asset clustered cost sensitivity.

Read only completed real 1H spot history through Edge V1. Both directional
counterfactual paths are frozen prior to outcomes; no Production mutation.
This is a descriptive reuse of historical dates already seen in Edge research,
NOT a fresh holdout or confirmed trading edge.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research.edge_event_ledger_v1 import HOUR_MS, HORIZON_H, build_ledger
from research.edge_real_market_baselines_v1 import (
    POLICIES, _policy_direction, asof_last_closed_hour, fetch_completed_1h,
)
from research.edge_real_market_regime_audit_v1 import SYMBOLS

SCHEMA = "ATLAS_EDGE_NONOVERLAP_COST_AUDIT_V1"
COST_BPS = (0, 5, 10, 17, 25)
BOOTSTRAP_SEED = 13018
BOOTSTRAP_ITERATIONS = 500
HOLDOUT_RATIO = 0.30
PURGE_HOURS = 24


def prepare_event_rows(ledgers):
    pairs = defaultdict(dict)
    for ledger in ledgers:
        if ledger.get("schema") != "ATLAS_EDGE_EVENT_LEDGER_V1":
            raise ValueError("Unknown event schema")
        for r in ledger["rows"]:
            key=(r["symbol"],r["event_at_ms"])
            if r["direction"] in pairs[key]:
                raise ValueError("Duplicate event direction")
            pairs[key][r["direction"]] = r
    if not pairs:
        raise ValueError("Empty event data")
    all_times = sorted({timestamp for (_, timestamp) in pairs})
    if len(all_times)<90:
        raise ValueError("Insufficient market event timestamps")
    # Choose one fixed 12h phase from the earliest 4h observation in the
    # complete universe; it is independent of outcomes and common across coins.
    phase = all_times[0] % (HORIZON_H * HOUR_MS)
    times = [t for t in all_times if t % (HORIZON_H * HOUR_MS) == phase]
    for t1,t2 in zip(times,times[1:]):
        if t2 - t1 != HORIZON_H * HOUR_MS:
            raise ValueError("Incomplete nonoverlapping event grid")
    cutoff = all_times[int(len(all_times) * (1 - HOLDOUT_RATIO))]
    selected = {"discovery":defaultdict(list),"holdout":defaultdict(list)}
    purged = 0
    unmatched = 0
    for (symbol, timestamp), by_direction in sorted(pairs.items()):
        if timestamp % (HORIZON_H * HOUR_MS) != phase:
            continue
        if set(by_direction) != {"LONG","SHORT"}:
            unmatched+=1
            continue
        anchor = by_direction["LONG"]
        if anchor["features"] != by_direction["SHORT"]["features"]:
            raise ValueError("Two directions have different observed features")
        if anchor["forward_matures_at_ms"] < cutoff - PURGE_HOURS * HOUR_MS:
            section="discovery"
        elif timestamp >= cutoff:
            section="holdout"
        else:
            purged+=1
            continue
        f=anchor["features"]
        for p in POLICIES:
            direction=_policy_direction(p,f)
            if direction:
                selected[section][p].append(by_direction[direction])
    return selected, {
        "original_4h_timestamps":len(all_times),
        "nonoverlap_12h_timestamps":len(times),
        "phase_ms":phase,
        "cutoff_ms":cutoff,
        "purged_asset_events":purged,
        "excluded_unpaired_asset_events":unmatched,
        "per_symbol_12h_path_overlap":False,
        "cross_symbol_btc_shock_dependence":True,
    }


def _per_unit_bps(row):
    s=row["settlement"]
    if s.get("gross_r") is None:
        return None
    opening=s.get("hypothetical_fill_open")
    stop=row["frozen_plan"]["stop_loss"]
    if opening is None or opening <= 0 or stop <= 0 or opening==stop:
        raise ValueError("Missing exact hypothetical entry-risk geometry")
    risk=abs(opening-stop)
    return opening / 10000 / risk


def _ci_by_day(values, iterations=BOOTSTRAP_ITERATIONS):
    """Resample UTC calendar-day clusters, not rows or coins individually.

    Diagnostic uncertainty only: historical dates reused for model inspection,
    so intervals are not prospective predictive confidence bounds.
    """
    grouped=defaultdict(list)
    for event_time, net_r in values:
        grouped[event_time // (24*HOUR_MS)].append(net_r)
    days=list(sorted(grouped))
    if len(days)<8:
        return None
    rng=random.Random(BOOTSTRAP_SEED)
    means=[]
    for _ in range(iterations):
        sample=[rng.choice(days) for _ in days]
        n=sum(len(grouped[d]) for d in sample)
        means.append(sum(sum(grouped[d]) for d in sample)/n)
    means.sort()
    lo=means[int(.025*(len(means)-1))]
    hi=means[int(.975*(len(means)-1))]
    return [round(lo,5),round(hi,5)]


def _evaluate(rows):
    observed=[]
    for row in rows:
        unit=_per_unit_bps(row)
        if unit is None:
            continue
        observed.append((row, unit))
    if not observed:
        return {
            "selected":len(rows),
            "settled":0,
            "excluded_ambiguous_or_gap":len(rows),
            "cost_scenarios":{},
            "breakeven_roundtrip_bps_descriptive":None,
        }
    cost_per_bp=sum(v for _,v in observed)/len(observed)
    gross_mean=sum(r["settlement"]["gross_r"] for r,_ in observed)/len(observed)
    breakeven=gross_mean/cost_per_bp if cost_per_bp else None
    scenarios={}
    for bps in COST_BPS:
        result=[(r, r["settlement"]["gross_r"]-bps*unit) for r,unit in observed]
        gains=[net for _,net in result if net>0]
        losses=[net for _,net in result if net<0]
        clustered=[(r["event_at_ms"],net) for r,net in result]
        scenarios[str(bps)]={
            "mean_net_r":round(sum(v for _,v in result)/len(result),5),
            "positive_pct":round(100*len(gains)/len(result),2),
            "profit_factor":round(sum(gains)/abs(sum(losses)),4) if losses else None,
            "calendar_day_cluster_ci95_descriptive":_ci_by_day(clustered),
            "cost_is_unverified_spot_scenario":True,
        }
    return {
        "selected":len(rows),
        "settled":len(observed),
        "excluded_ambiguous_or_gap":len(rows)-len(observed),
        "gross_mean_r":round(gross_mean,5),
        "breakeven_roundtrip_bps_descriptive":round(breakeven,3) if breakeven is not None else None,
        "cost_scenarios":scenarios,
    }


def compare(ledgers):
    selected,info=prepare_event_rows(ledgers)
    result={part:{p:_evaluate(selected[part][p]) for p in POLICIES}
            for part in ("discovery","holdout")}
    return {"schema":SCHEMA,
            "periods":result,
            "split":info,
            "cost_basis":"FIXED_GROSS_FIRST_TOUCH_REPRICED_AT_BPS_SCENARIOS",
            "cost_scenarios_bps":list(COST_BPS),
            "confidence_intervals_are_cluster_descriptive_only":True,
            "reused_historical_holdout_not_blind":True,
            "research_only":True,
            "can_change_production":False,
            "can_create_trade":False,
            "can_override_final_trade_gate":False,
            "profitability_validated":False}


def run(symbols, days=90, as_of_ms=None, fetcher=fetch_completed_1h):
    if not symbols or "BTCUSDT" not in symbols or len(set(symbols))!=len(symbols):
        raise ValueError("Research requires BTC and no duplicate symbols")
    if days<60 or days>180:
        raise ValueError("Invalid study window")
    as_of_ms=asof_last_closed_hour(int(time.time()*1000)) if as_of_ms is None else as_of_ms
    btc,bmeta=fetcher("BTCUSDT",days,as_of_ms)
    if not bmeta.get("continuity_validated") or len(btc)!=days*24:
        raise ValueError("BTC source incomplete")
    ledgers=[]
    sources=[bmeta]
    for sym in symbols:
        if sym=="BTCUSDT":
            bars=btc
        else:
            bars,meta=fetcher(sym,days,as_of_ms)
            if not meta.get("continuity_validated") or len(bars)!=days*24:
                raise ValueError("Asset source incomplete")
            sources.append(meta)
        ledgers.append(build_ledger(sym,bars,btc,as_of_ms,modeled_cost_bps=None))
    report=compare(ledgers)
    report.update({
        "symbols":list(symbols), "days":days,
        "as_of_ms":as_of_ms,
        "data_quality":sources,
        "hypothetical_geometry":"1.5ATR_STOP_2.5R_TP_NEXT_HOUR_OPEN",
        "funding_and_spread_not_measured":True,
        "overlapping_positions_across_assets_not_accounted":True,
        "venue_trade_costs_unverified":True,
        "no_prospective_evidence":True,
    })
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbols",default=",".join(SYMBOLS))
    ap.add_argument("--days",type=int,default=90)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    result=run([x.strip().upper() for x in args.symbols.split(",") if x.strip()],args.days)
    p=Path(args.output)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"schema":SCHEMA,
                      "holdout":{p:{k:v for k,v in result["periods"]["holdout"][p].items() if k!="cost_scenarios"}
                                  | {"net_17bps":result["periods"]["holdout"][p]["cost_scenarios"]["17"]["mean_net_r"],
                                     "cluster_ci95_17bps":result["periods"]["holdout"][p]["cost_scenarios"]["17"]["calendar_day_cluster_ci95_descriptive"]}
                                 for p in POLICIES}},sort_keys=True))


if __name__=="__main__":
    main()
