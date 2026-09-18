#!/usr/bin/env python3
"""Prospective candle-path replay for ATLAS pre-registered shadow hypotheses.

Implements only the two path-changing hypotheses registered before evaluation:
DELAY_ENTRY_1H_CONFIRM and EARLY_MOMENTUM_FAILFAST_EXIT. Uses post-decision
public candles, never future information at decision time, never mutates the
Champion, and never selects a best variant for Production.
"""
from __future__ import annotations
import datetime as dt
import json, math
from pathlib import Path
from typing import Any

from offline_production_path_settlement import market_klines, event_from

VERSION="ATLAS_OPPORTUNITY_PATH_REPLAY_V1"
SOURCE_SCHEMA="ATLAS_PRODUCTION_VALIDATION_SCORECARD_V1"
EPOCH_ID="HTF_SR_V2_2026-09-14"
ACTIVATION_AT="2026-09-18T07:10:00+00:00"
THRESHOLD=68
HORIZON_H=12
MIN_N=30
FEE_BPS_PER_SIDE=5.0
SLIPPAGE_BPS_PER_SIDE=3.0
FUNDING_BPS_PER_12H=1.0
FAILFAST_ADVERSE_R=-0.25
FAILFAST_WINDOW_H=4

PATH_HYPOTHESES=(
 {"id":"DELAY_ENTRY_1H_CONFIRM","rule":"first fully post-decision clock-aligned 1H candle must close in trade direction; enter at its close using original quantity and absolute SL/TP","shadow_action":"REPRICE_ENTRY"},
 {"id":"EARLY_MOMENTUM_FAILFAST_EXIT","rule":"before TP1/SL, exit at first fully post-decision 1H close within first 4H at <= -0.25 original R","shadow_action":"REPRICE_EXIT"},
)


def _read(root:Path,name:str):
    try:return json.loads((root/"status"/name).read_text(encoding="utf-8"))
    except Exception:return {}


def _iso(v):
    try:
        x=dt.datetime.fromisoformat(str(v).replace("Z","+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
    except Exception:return None


def _f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None


def _next_full_hour_ms(captured_ms:int)->int:
    hour=3_600_000
    return ((captured_ms+hour-1)//hour)*hour


def _cost_usd(notional:float, holding_h:float)->float:
    bps=2*(FEE_BPS_PER_SIDE+SLIPPAGE_BPS_PER_SIDE)+FUNDING_BPS_PER_12H*(max(0,min(12,holding_h))/12)
    return notional*bps/10_000.0


def _directional_pnl(direction,qty,entry,exit_price):
    return qty*(exit_price-entry) if direction=="LONG" else qty*(entry-exit_price)


def _bar_close(bar):
    return _f(bar.get("close"))


def _full_hour_bars(candles,start_ms,end_ms):
    """Aggregate only complete clock-aligned hours from 5m candles."""
    by={}
    for x in candles:
        t=int(x["open_time"])
        h=(t//3_600_000)*3_600_000
        if h < start_ms or h+3_600_000 > end_ms: continue
        by.setdefault(h,[]).append(x)
    out=[]
    for h,rows in sorted(by.items()):
        rows=sorted(rows,key=lambda x:int(x["open_time"]))
        # require all 12 expected 5m opens: fail closed on missing data
        expected=[h+i*300_000 for i in range(12)]
        if [int(x["open_time"]) for x in rows] != expected: continue
        out.append({"open_time":h,"close_time":h+3_600_000,
                    "open":float(rows[0]["open"]),"close":float(rows[-1]["close"]),
                    "high":max(float(x["high"]) for x in rows),"low":min(float(x["low"]) for x in rows)})
    return out


def _first_terminal(candles,g):
    ev,candle,tp1_seen=event_from(candles,g)
    if ev in {"SL","TP2","AMBIGUOUS"} and candle:
        return ev,int(candle["open_time"]),tp1_seen
    return None,None,tp1_seen


def _champion_exit(candles,g,end_ms):
    ev,t,tp1=_first_terminal(candles,g)
    if ev=="AMBIGUOUS": return {"state":"AMBIGUOUS_FAIL_CLOSED"}
    if ev=="SL": return {"state":"SETTLED","exit_price":float(g["stop_loss"]),"exit_at_ms":t,"terminal":"SL","tp1_reached":bool(tp1)}
    if ev=="TP2": return {"state":"SETTLED","exit_price":float(g["tp2"]),"exit_at_ms":t,"terminal":"TP2","tp1_reached":True}
    if not candles:return {"state":"MARKET_DATA_UNAVAILABLE"}
    return {"state":"SETTLED","exit_price":float(candles[-1]["close"]),"exit_at_ms":min(end_ms,int(candles[-1]["open_time"])+300_000),
            "terminal":"HORIZON_CLOSE","tp1_reached":bool(tp1)}


def _eligible(row,cost_map):
    p=row.get("decision_provenance"); s=row.get("settlement") or {}; g=row.get("geometry") or {}
    cap=_iso(row.get("captured_at")); activation=_iso(ACTIVATION_AT)
    did=str(row.get("decision_id") or row.get("id") or "")
    if not did or not cap or cap<activation:return False
    if not isinstance(p,dict) or p.get("frozen_before_outcome") is not True:return False
    if p.get("strategy_epoch_id")!=EPOCH_ID or p.get("product_horizon")!="4-12H" or p.get("production_threshold_locked")!=68:return False
    if s.get("terminal") is not True or (cost_map.get(did) or {}).get("net_r") is None:return False
    return all(_f(g.get(k)) is not None for k in ("entry","stop_loss","tp1","tp2","risk_abs")) and str(row.get("direction")) in {"LONG","SHORT"}


def replay_delay(row,candles):
    g=dict(row["geometry"]); start=int(row["captured_at_ms"]); end=start+HORIZON_H*3_600_000
    hour_start=_next_full_hour_ms(start)
    hours=_full_hour_bars(candles,hour_start,end)
    if not hours:return {"state":"MARKET_DATA_INCOMPLETE"}
    h=hours[0]; direction=row["direction"]
    confirms=(h["close"]>h["open"]) if direction=="LONG" else (h["close"]<h["open"])
    if not confirms:return {"state":"SHADOW_SKIP_NO_1H_CONFIRM","confirmation_hour_open_ms":h["open_time"],"confirmation_close":h["close"]}
    new_entry=float(h["close"]); stop=float(g["stop_loss"]); tp1=float(g["tp1"]); tp2=float(g["tp2"])
    valid=(stop<new_entry<tp1<tp2) if direction=="LONG" else (stop>new_entry>tp1>tp2)
    if not valid:return {"state":"SHADOW_SKIP_GEOMETRY_INVALID_AT_DELAYED_ENTRY","delayed_entry":new_entry}
    after=[x for x in candles if int(x["open_time"])>=h["close_time"]]
    gg={**g,"entry":new_entry,"risk_abs":abs(new_entry-stop)}
    out=_champion_exit(after,gg,end)
    if out.get("state")!="SETTLED":return {**out,"delayed_entry":new_entry}
    qty=float(row.get("paper_quantity") or 0); risk=float(row.get("risk_usd") or 0)
    if qty<=0 or risk<=0:return {"state":"SIZING_UNAVAILABLE"}
    holding=max(0,(out["exit_at_ms"]-h["close_time"])/3_600_000)
    gross_usd=_directional_pnl(direction,qty,new_entry,float(out["exit_price"]))
    notional=abs(qty*new_entry); cost=_cost_usd(notional,holding); net=gross_usd-cost
    return {**out,"state":"SETTLED","delayed_entry":round(new_entry,12),"entry_at_ms":h["close_time"],
            "holding_h":round(holding,4),"gross_pnl_usd":round(gross_usd,4),"estimated_cost_usd":round(cost,4),
            "net_pnl_usd":round(net,4),"net_r":round(net/risk,4),
            "confirmation_hour_open_ms":h["open_time"],"same_quantity_as_champion":True}


def replay_failfast(row,candles):
    g=row["geometry"]; start=int(row["captured_at_ms"]); end=start+HORIZON_H*3_600_000
    champion=_champion_exit(candles,g,end)
    if champion.get("state")!="SETTLED":return champion
    hour_start=_next_full_hour_ms(start); hours=_full_hour_bars(candles,hour_start,min(end,start+FAILFAST_WINDOW_H*3_600_000))
    risk_abs=float(g["risk_abs"]); entry=float(g["entry"]); direction=row["direction"]
    exit_at=None; exit_price=None
    for h in hours:
        pre=[x for x in candles if int(x["open_time"])<h["close_time"]]
        ev,t,tp1=_first_terminal(pre,g)
        if ev in {"SL","TP2","AMBIGUOUS"} or tp1: break
        close=float(h["close"])
        adverse=((close-entry)/risk_abs) if direction=="LONG" else ((entry-close)/risk_abs)
        if adverse<=FAILFAST_ADVERSE_R:
            exit_at=h["close_time"];exit_price=close;break
    if exit_at is None:return {"state":"NO_FAILFAST_TRIGGER","champion_terminal":champion.get("terminal")}
    qty=float(row.get("paper_quantity") or 0); risk=float(row.get("risk_usd") or 0)
    if qty<=0 or risk<=0:return {"state":"SIZING_UNAVAILABLE"}
    holding=max(0,(exit_at-start)/3_600_000); gross=_directional_pnl(direction,qty,entry,exit_price)
    notional=abs(qty*entry); cost=_cost_usd(notional,holding); net=gross-cost
    return {"state":"SETTLED","terminal":"FAILFAST_EXIT","exit_price":round(exit_price,12),"exit_at_ms":exit_at,
            "holding_h":round(holding,4),"gross_pnl_usd":round(gross,4),"estimated_cost_usd":round(cost,4),
            "net_pnl_usd":round(net,4),"net_r":round(net/risk,4),"adverse_trigger_r":FAILFAST_ADVERSE_R,
            "champion_terminal":champion.get("terminal")}


def build(root:Path):
    v=_read(root,"production-validation-latest.json")
    if v.get("schema")!=SOURCE_SCHEMA:raise RuntimeError("unexpected scorecard schema")
    if (v.get("epoch") or {}).get("id")!=EPOCH_ID:raise RuntimeError("unexpected epoch")
    if (v.get("safety") or {}).get("production_threshold")!=68:raise RuntimeError("threshold drift")
    cost_rows=(v.get("post_v2_cost_adjusted") or {}).get("rows") or []
    cost={str(x.get("decision_id")):x for x in cost_rows if x.get("decision_id")}
    eligible=[x for x in v.get("rows") or [] if _eligible(x,cost)]
    results={h["id"]:[] for h in PATH_HYPOTHESES}; data_errors=[]
    for row in eligible:
        start=int(row["captured_at_ms"]); end=start+HORIZON_H*3_600_000
        try:
            candles,provider=market_klines(row["symbol"],"5",start,end)
            if not candles:raise RuntimeError("no 5m candles")
        except Exception as exc:
            data_errors.append({"decision_id":row.get("decision_id"),"symbol":row.get("symbol"),"error":f"{type(exc).__name__}: {exc}"})
            continue
        champion=(cost.get(str(row.get("decision_id"))) or {}).get("net_r")
        for h in PATH_HYPOTHESES:
            out=replay_delay(row,candles) if h["id"]=="DELAY_ENTRY_1H_CONFIRM" else replay_failfast(row,candles)
            # Pair every evaluable policy decision, not only trades whose path changed.
            # SKIP => 0R shadow contribution; NO_TRIGGER => Champion unchanged.
            shadow_net_r=out.get("net_r")
            policy_effect="REPRICED_PATH" if shadow_net_r is not None else None
            if h["id"]=="DELAY_ENTRY_1H_CONFIRM" and str(out.get("state") or "").startswith("SHADOW_SKIP_"):
                shadow_net_r=0.0; policy_effect="SKIPPED_BY_SHADOW_POLICY"
            elif h["id"]=="EARLY_MOMENTUM_FAILFAST_EXIT" and out.get("state")=="NO_FAILFAST_TRIGGER" and champion is not None:
                shadow_net_r=float(champion); policy_effect="UNCHANGED_CHAMPION_PATH"
            results[h["id"]].append({"decision_id":row.get("decision_id"),"symbol":row.get("symbol"),"direction":row.get("direction"),
                                     "captured_at":row.get("captured_at"),"provider":provider,
                                     "champion_net_r":champion,"shadow_net_r":shadow_net_r,"policy_effect":policy_effect,**out})
    reports=[]
    for h in PATH_HYPOTHESES:
        rr=results[h["id"]]
        paired=[x for x in rr if x.get("shadow_net_r") is not None and x.get("champion_net_r") is not None]
        changed=[x for x in paired if x.get("policy_effect") in {"REPRICED_PATH","SKIPPED_BY_SHADOW_POLICY"}]
        delta=sum(float(x["shadow_net_r"])-float(x["champion_net_r"]) for x in paired)
        reports.append({**h,"state":"FORMAL_SHADOW_SAMPLE_READY" if len(paired)>=MIN_N else "COLLECTING_PATH_REPLAY",
                        "eligible":len(eligible),"evaluable":len(paired),"changed":len(changed),"paired_n":len(paired),"min_n":MIN_N,
                        "formal_ready":len(paired)>=MIN_N,
                        "champion_net_r":round(sum(float(x["champion_net_r"]) for x in paired),4) if paired else None,
                        "shadow_net_r":round(sum(float(x["shadow_net_r"]) for x in paired),4) if paired else None,
                        "delta_net_r":round(delta,4) if paired else None,
                        "promotion_allowed":False,"production_impact":"NONE","rows":rr})
    return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"activation_at":ACTIVATION_AT,
            "epoch_id":EPOCH_ID,"product_horizon":"4-12H","criteria_locked_before_evaluation":True,
            "path_rules":{"delay_entry_confirmation":"FIRST_FULL_POST_DECISION_CLOCK_ALIGNED_1H_DIRECTIONAL_CLOSE",
                          "failfast_adverse_r":FAILFAST_ADVERSE_R,"failfast_window_h":FAILFAST_WINDOW_H,
                          "intrabar_ambiguity":"FAIL_CLOSED","delayed_entry_position_size":"ORIGINAL_CHAMPION_QUANTITY"},
            "cost_model":{"fee_bps_per_side":FEE_BPS_PER_SIDE,"slippage_bps_per_side":SLIPPAGE_BPS_PER_SIDE,
                          "funding_bps_per_12h":FUNDING_BPS_PER_12H,"production_impact":"NONE"},
            "eligible_prospective_rows":len(eligible),"market_data_errors":data_errors,"hypotheses":reports,
            "interpretation":{"causal_claim_allowed":False,"best_variant_selection_allowed":False,
                              "automatic_strategy_change":False,"automatic_promotion":False,
                              "formal_comparison_requires_paired_n":MIN_N},
            "safety":{"research_only":True,"paper_only":True,"live_execution":False,"can_override_production":False,
                      "can_change_threshold":False,"production_threshold":68,"production_impact":"NONE"}}


def validate(x):
    assert x["schema"]==VERSION and x["criteria_locked_before_evaluation"] is True
    assert x["epoch_id"]==EPOCH_ID and x["safety"]["production_threshold"]==68
    assert x["safety"]["can_override_production"] is False
    assert x["interpretation"]["best_variant_selection_allowed"] is False
    assert all(h["promotion_allowed"] is False for h in x["hypotheses"])


def main():
    root=Path(__file__).resolve().parent;x=build(root);validate(x)
    out=root/"status/opportunity-path-replay-latest.json"
    out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"eligible":x["eligible_prospective_rows"],"errors":len(x["market_data_errors"]),"out":str(out)}))
    return 0
if __name__=="__main__":raise SystemExit(main())
