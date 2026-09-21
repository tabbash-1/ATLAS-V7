#!/usr/bin/env python3
"""Canonical WAIT missed-opportunity forward settlement.

Research-only observability. Reads immutable canonical Production snapshots and
settles WAIT decisions against public 5m candles at 1/2/4/8/12h. It never changes
Production score, threshold, decision, execution, or risk.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math
import pathlib
from collections import defaultdict
from typing import Any

from offline_production_path_settlement import market_klines

ROOT = pathlib.Path(__file__).resolve().parent
HISTORY = ROOT / "status/history/production-snapshots.jsonl"
LATEST = ROOT / "status/wait-missed-opportunity-latest.json"
LEDGER = ROOT / "status/history/wait-missed-opportunity.jsonl"
SCHEMA = "ATLAS_WAIT_MISSED_OPPORTUNITY_V3_EXECUTABILITY_AWARE"
HORIZONS = (1, 2, 4, 8, 12)
ROUND_TRIP_FEE_SLIPPAGE_BPS = 16
FUNDING_BPS_PER_12H = 1
CORE = {"BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"}
# Strategy-semantic boundary: HTF neutral-regime V2 merged to main.
POST_V2_EPOCH_ID = "HTF_SR_V2_2026-09-14"
POST_V2_START = dt.datetime(2026, 9, 14, 12, 31, 29, tzinfo=dt.timezone.utc)
POST_V2_RELEASE_SHA = "0e3db49b3511f845e4df52db49d41700d14a4eee"


def fnum(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None


def parse_time(v): return dt.datetime.fromisoformat(str(v).replace("Z","+00:00"))


def canonical_truth(d):
    t=(d or {}).get("canonical_decision") or {}
    if t.get("schema") != "ATLAS_CANONICAL_DECISION_TRUTH_V1": return None
    if t.get("canonical_source_present") is not True or t.get("source_of_truth") != "FINAL_TRADE_GATE": return None
    return t


def observed_price(d):
    for src in ((d or {}).get("indicators") or {}, d or {}):
        for k in ("price","current_price","market_price","last_price","close"):
            x=fnum(src.get(k))
            if x and x>0:return x
    pa=((d or {}).get("timeframe_matrix") or {}).get("htf_price_action") or {}
    for frame in ("1h","4h","12h"):
        x=fnum(((pa.get("frames") or {}).get(frame) or {}).get("price"))
        if x and x>0:return x
    return None


def frozen_trade_geometry(d, direction):
    plan=(d or {}).get("trade_plan") or {}
    entry=fnum(plan.get("entry") or observed_price(d))
    stop=fnum(plan.get("stop_loss") or (d or {}).get("stop_loss"))
    tp=fnum(plan.get("tp2") or (d or {}).get("tp2"))
    if not entry or not stop or not tp:return None
    valid=(direction=="LONG" and stop<entry<tp) or (direction=="SHORT" and tp<entry<stop)
    if not valid:return None
    risk=abs(entry-stop)
    return {"entry":entry,"stop":stop,"tp2":tp,"gross_rr":abs(tp-entry)/risk if risk else None}


def independent_transition_evidence(d, direction):
    def aligned(reg):
        name=str((reg or {}).get("regime") or "").upper()
        return (any(x in name for x in ("UP","BULL")) and "DOWN" not in name) if direction=="LONG" else (any(x in name for x in ("DOWN","BEAR")) and "UP" not in name)
    asset=(d or {}).get("independent_market_regime") or {}
    btc=(d or {}).get("independent_btc_regime") or {}
    matrix=(d or {}).get("timeframe_matrix") or {}
    h1=str(matrix.get("1h") or matrix.get("1H") or (d or {}).get("bias_1h") or "").upper()
    h4=str(matrix.get("4h") or matrix.get("4H") or (d or {}).get("bias_4h") or "").upper()
    h12=str(matrix.get("12h") or matrix.get("12H") or (d or {}).get("bias_12h") or "").upper()
    d1=str(matrix.get("1d") or matrix.get("1D") or (d or {}).get("bias_1d") or "").upper()
    opposite="SHORT" if direction=="LONG" else "LONG"
    return {"asset_regime_aligned":aligned(asset),"btc_regime_aligned":aligned(btc),"h1_aligned":direction in h1,"h4_aligned":direction in h4,"h12_explicit_opposition":opposite in h12,"d1_explicit_opposition":opposite in d1}


def invalidation_price(d, direction):
    plan=(d or {}).get("trade_plan") or {}
    x=fnum(plan.get("stop_loss") or (d or {}).get("stop_loss"))
    if not x:return None
    p=observed_price(d)
    if not p:return None
    if direction=="LONG" and x>=p:return None
    if direction=="SHORT" and x<=p:return None
    return x


def blocker_family(d,t):
    v2=(d or {}).get("htf_sr_decision_v2") or {}
    final=(d or {}).get("final_trade_gate") or {}
    blocks=v2.get("blockers") or final.get("blockers") or []
    raw=str(t.get("raw_wait_reason") or (d or {}).get("wait_reason") or "UNKNOWN")
    primary=str(v2.get("primary_blocker") or final.get("primary_blocker") or raw)
    joined="|".join([primary,raw]+[str(x) for x in blocks]).upper()
    for key,needles in (
        ("HTF_CONFLICT",("HTF_","1D_","12H","4H_")),
        ("SCORE_BELOW_THRESHOLD",("SCORE","NOT_QUALIFIED")),
        ("BREAKOUT_NOT_CONFIRMED",("BREAKOUT",)),
        ("SETUP_QUALITY",("SETUP_QUALITY","FORWARD_EVIDENCE")),
        ("GEOMETRY_RR",("GEOMETRY","RR_")),
        ("VOLUME",("VOLUME",)),
        ("FUTURES",("FUTURES","DERIVATIVES")),
    ):
        if any(n in joined for n in needles):return key
    return primary or "OTHER"


def load_waits():
    rows=[]; seen=set()
    if not HISTORY.exists():return rows
    for line in HISTORY.read_text().splitlines():
        try:r=json.loads(line); at=parse_time(r["captured_at"])
        except Exception:continue
        for symbol,d in (r.get("decisions") or {}).items():
            if symbol not in CORE or not isinstance(d,dict) or not d.get("ok"):continue
            t=canonical_truth(d)
            if not t or t.get("trade_ready") is True:continue
            direction=str(d.get("candidate_direction") or d.get("product_direction") or "").upper()
            if direction not in {"LONG","SHORT"}:continue
            price=observed_price(d)
            if not price:continue
            did=str(t.get("decision_id") or "")
            key=did or hashlib.sha256(f"{symbol}|{at.isoformat()}|{direction}|{price}".encode()).hexdigest()[:24]
            if key in seen:continue
            seen.add(key)
            rows.append({"id":key,"decision_id":did or None,"symbol":symbol,"captured_at":at,"captured_at_ms":int(at.timestamp()*1000),"direction":direction,"price":price,"invalidation":invalidation_price(d,direction),"geometry":frozen_trade_geometry(d,direction),"transition_evidence":independent_transition_evidence(d,direction),"score":fnum(t.get("score")),"threshold":fnum(t.get("threshold")),"reason":t.get("wait_reason"),"raw_reason":t.get("raw_wait_reason"),"blocker_family":blocker_family(d,t),"playbook":d.get("playbook"),"release":((r.get("runtime") or {}).get("release") or (r.get("runtime") or {}).get("commit_sha")),"v2_regime":((d.get("htf_sr_decision_v2") or {}).get("regime")),"epoch_id":POST_V2_EPOCH_ID if at >= POST_V2_START else "LEGACY_BASELINE"})
    return rows


def settle(row, now):
    start=row["captured_at_ms"]; maturity=start+12*3600_000
    out={k:v for k,v in row.items() if k not in {"captured_at","captured_at_ms"}}
    out["captured_at"]=row["captured_at"].isoformat(); out["horizons"]={}; out.update({"research_only":True,"can_override_production":False,"live_execution":False})
    if int(now.timestamp()*1000) < start+3600_000:
        out["status"]="OPEN"; return out
    end=min(int(now.timestamp()*1000),maturity)
    try:candles,provider=market_klines(row["symbol"],"5",start,end)
    except Exception as e:
        out.update({"status":"MARKET_DATA_ERROR","error":str(e)[:500]}); return out
    if not candles:
        out["status"]="MARKET_DATA_ERROR"; out["error"]="no_candles"; return out
    p0=row["price"]; direction=row["direction"]; inv=row["invalidation"]
    for h in HORIZONS:
        h_end=start+h*3600_000
        if int(now.timestamp()*1000)<h_end:continue
        cs=[c for c in candles if int(c["open_time"]) < h_end]
        if not cs:continue
        last=cs[-1]["close"]; change=(last/p0-1)*100; directional=change if direction=="LONG" else -change
        highs=[c["high"] for c in cs]; lows=[c["low"] for c in cs]
        mfe=((max(highs)/p0-1)*100) if direction=="LONG" else ((p0/min(lows)-1)*100)
        mae=((p0/min(lows)-1)*100) if direction=="LONG" else ((max(highs)/p0-1)*100)
        invalidated=False
        if inv is not None:
            invalidated=any((c["low"]<=inv if direction=="LONG" else c["high"]>=inv) for c in cs)
        out["horizons"][f"{h}h"]={"close":round(last,10),"directional_return_pct":round(directional,4),"mfe_pct":round(mfe,4),"mae_pct":round(mae,4),"invalidation_hit":invalidated}
    out["market_source"]=provider
    h4=out["horizons"].get("4h"); h8=out["horizons"].get("8h"); h12=out["horizons"].get("12h")
    mature=h12 or h8 or h4
    if mature:
        out["missed_opportunity"] = bool(mature["mfe_pct"] >= 1.0 and not mature["invalidation_hit"])
        out["classification_rule"]="LEGACY_RESEARCH_ONLY_MFE_GE_1PCT_WITHOUT_INVALIDATION"
        g=row.get("geometry"); ev=row.get("transition_evidence") or {}
        if not g:
            out["executability_classification"]="GOOD_WAIT"; out["executability_reason"]="NO_FROZEN_VALID_GEOMETRY"
        else:
            risk=abs(g["entry"]-g["stop"]); total_cost_bps=ROUND_TRIP_FEE_SLIPPAGE_BPS+FUNDING_BPS_PER_12H
            cost_r=(g["entry"]*(total_cost_bps/10000.0))/risk if risk else None
            net_rr=(g["gross_rr"]-(cost_r or 0)) if g.get("gross_rr") is not None else None
            independent_ok=ev.get("asset_regime_aligned") and ev.get("btc_regime_aligned") and ev.get("h1_aligned") and ev.get("h4_aligned") and not ev.get("h12_explicit_opposition") and not ev.get("d1_explicit_opposition")
            out["net_rr_after_locked_cost"]=round(net_rr,4) if net_rr is not None else None; out["locked_cost_bps_12h"]=total_cost_bps
            if out["missed_opportunity"] and independent_ok and net_rr is not None and net_rr>=2.0:
                out["executability_classification"]="MISSED_TRADEABLE_OPPORTUNITY"; out["executability_reason"]="T0_INDEPENDENT_TRANSITION_ALIGNED_NET_RR_GE_2"
            elif out["missed_opportunity"]:
                out["executability_classification"]="CORRECT_NO_CHASE"; out["executability_reason"]="MOVE_OCCURRED_BUT_T0_LOCKED_EXECUTABILITY_NOT_PROVEN"
            else:
                out["executability_classification"]="GOOD_WAIT"; out["executability_reason"]="NO_QUALIFYING_FORWARD_OPPORTUNITY"
    else:
        out["missed_opportunity"]=None; out["executability_classification"]=None
    out["status"]="MATURED" if h12 else "PARTIAL"
    return out


def summarize(records):
    matured=[r for r in records if r.get("missed_opportunity") is not None]
    groups=defaultdict(list)
    for r in matured:groups[r.get("blocker_family") or "OTHER"].append(r)
    by={}
    for k,rs in groups.items():
        by[k]={"n":len(rs),"missed_n":sum(bool(r.get("missed_opportunity")) for r in rs),"missed_rate_pct":round(100*sum(bool(r.get("missed_opportunity")) for r in rs)/len(rs),2)}
        for h in (4,8,12):
            vals=[r["horizons"][f"{h}h"]["directional_return_pct"] for r in rs if f"{h}h" in r.get("horizons",{})]
            by[k][f"mean_{h}h_directional_return_pct"]=round(sum(vals)/len(vals),4) if vals else None
    return {"records":len(records),"matured_classified":len(matured),"missed_n":sum(bool(r.get("missed_opportunity")) for r in matured),"missed_rate_pct":round(100*sum(bool(r.get("missed_opportunity")) for r in matured)/len(matured),2) if matured else None,"by_blocker_family":dict(sorted(by.items()))}


def cohort_summary(records):
    legacy=[r for r in records if r.get("epoch_id")=="LEGACY_BASELINE"]
    post=[r for r in records if r.get("epoch_id")==POST_V2_EPOCH_ID]
    neutral=[r for r in post if r.get("v2_regime")=="4H_DIRECTIONAL_12H_NEUTRAL"]
    return {
        "legacy_baseline": summarize(legacy),
        "post_v2_forward": summarize(post),
        "post_v2_neutral_regime": summarize(neutral),
    }


def main():
    now=dt.datetime.now(dt.timezone.utc); waits=load_waits(); records=[]
    for row in waits[-300:]:records.append(settle(row,now))
    report={"schema":SCHEMA,"generated_at":now.isoformat(),"decision_source_of_truth":"FINAL_TRADE_GATE","product_horizon":"4-12H","evaluation_horizons_h":list(HORIZONS),"classification_is_research_only":True,"production_threshold_unchanged":68,"can_change_threshold":False,"can_override_production":False,"live_execution":False,"performance_epoch":{"id":POST_V2_EPOCH_ID,"start_at":POST_V2_START.isoformat(),"release_sha":POST_V2_RELEASE_SHA,"policy":"legacy and post-V2 evidence must never be mixed for current-version claims"},"methodology":"Canonical WAIT capture; observed market price at decision time; public 5m candles; exact 1/2/4/8/12h close/MFE/MAE; invalidation-aware descriptive missed-opportunity classification.","summary":summarize(records),"cohorts":cohort_summary(records),"records":records}
    LATEST.parent.mkdir(parents=True,exist_ok=True); LATEST.write_text(json.dumps(report,indent=2,sort_keys=True))
    LEDGER.parent.mkdir(parents=True,exist_ok=True); LEDGER.write_text("\n".join(json.dumps(r,separators=(",",":"),sort_keys=True) for r in records)+( "\n" if records else ""))
    print(json.dumps({"schema":SCHEMA,"summary":report["summary"],"cohorts":report["cohorts"]},indent=2))

if __name__=="__main__":main()
