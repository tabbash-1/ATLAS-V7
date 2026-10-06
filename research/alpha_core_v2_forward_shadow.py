#!/usr/bin/env python3
"""Prospective forward evidence for ATLAS Alpha Core V2.

Research-only and append-only by decision timestamp/symbol. The module freezes
Alpha Core V2 LONG/SHORT/WAIT decisions using only information available at the
decision time, then settles the same frozen decision at 4H/8H/12H.

It has no authority over Production, Final Trade Gate, thresholds, geometry,
paper enrollment, or execution.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from historical_core_4_12h_replay import fetch_1h
from research.alpha_core_v2 import VERSION as ALPHA_VERSION, analyze as alpha_analyze

VERSION="ATLAS_ALPHA_CORE_V2_FORWARD_SHADOW_V2_FRESH_RUNTIME_CAPTURE"
LEDGER_SCHEMA="ATLAS_ALPHA_CORE_V2_FORWARD_LEDGER_V1"
HOUR_MS=60*60*1000
MIN_CAPTURE_SPACING_MS=4*HOUR_MS
HORIZONS=(4,8,12)
DEADBAND_ATR=0.35
SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT")


def _iso(ms):
    return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc).isoformat()


def _closed_rows(rows,now_ms):
    return [x for x in sorted(rows or [],key=lambda z:int(z["t"])) if int(x["t"])+HOUR_MS<=int(now_ms)]


def _last_decision_at(entries,symbol):
    xs=[int(x.get("decision_at_ms") or 0) for x in entries if x.get("symbol")==symbol]
    return max(xs) if xs else None


def _actual(entry_close,future_close,atr_at_entry):
    move=float(future_close)-float(entry_close)
    band=DEADBAND_ATR*float(atr_at_entry)
    if move>band:return "LONG"
    if move<-band:return "SHORT"
    return "WAIT"


def _metrics(records):
    out={"n":len(records)}
    if not records:return out
    labels=("LONG","SHORT","WAIT")
    cm={p:{a:0 for a in labels} for p in labels}
    for r in records:cm[r["prediction"]][r["actual"]]+=1
    directional=[r for r in records if r["prediction"]!="WAIT"]
    correct=sum(r["prediction"]==r["actual"] for r in records)
    dcorrect=sum(r["prediction"]==r["actual"] for r in directional)
    opposite=sum(
        r["prediction"] in ("LONG","SHORT")
        and r["actual"] in ("LONG","SHORT")
        and r["prediction"]!=r["actual"]
        for r in records
    )
    out.update({
        "accuracy_pct":round(100*correct/len(records),3),
        "directional_calls":len(directional),
        "directional_precision_pct":round(100*dcorrect/len(directional),3) if directional else None,
        "opposite_direction_pct_of_calls":round(100*opposite/len(directional),3) if directional else None,
        "wait_rate_pct":round(100*sum(r["prediction"]=="WAIT" for r in records)/len(records),3),
        "confusion":cm,
    })
    return out


def _load(path):
    p=Path(path)
    if not p.exists():
        return {
            "schema":LEDGER_SCHEMA,
            "entries":[],
            "alpha_version":ALPHA_VERSION,
            "research_only":True,
            "shadow_only":True,
            "live_execution":False,
            "production_effect":"NONE",
            "can_override_production":False,
            "can_override_final_gate":False,
        }
    x=json.loads(p.read_text())
    if x.get("schema")!=LEDGER_SCHEMA:
        raise RuntimeError("LEDGER_SCHEMA_MISMATCH")
    x.setdefault("entries",[])
    return x


def _settle(entry,rows_by_t):
    outcomes=entry.setdefault("outcomes",{})
    for h in HORIZONS:
        key=f"{h}h"
        if key in outcomes:continue
        target_t=int(entry["decision_bar_t"])+h*HOUR_MS
        bar=rows_by_t.get(target_t)
        if not bar:continue
        actual=_actual(entry["decision_close"],bar["c"],entry["atr14"])
        outcomes[key]={
            "horizon_h":h,
            "target_bar_t":target_t,
            "target_close":float(bar["c"]),
            "actual":actual,
            "prediction":entry["prediction"],
            "correct":entry["prediction"]==actual,
            "settled_at":_iso(target_t+HOUR_MS),
        }


def run(now_ms=None,fetcher=fetch_1h,
        ledger_path="status/alpha-core-v2-forward-ledger.json",
        latest_path="status/alpha-core-v2-forward-shadow-latest.json"):
    now_ms=int(now_ms if now_ms is not None else time.time()*1000)
    ledger=_load(ledger_path)
    entries=ledger["entries"]
    known={x.get("id") for x in entries}
    rows_cache={}
    captured=[]

    btc_rows=_closed_rows(fetcher("BTCUSDT",35,now_ms),now_ms)
    rows_cache["BTCUSDT"]=btc_rows

    for symbol in SYMBOLS:
        rows=btc_rows if symbol=="BTCUSDT" else _closed_rows(fetcher(symbol,35,now_ms),now_ms)
        if not rows:continue
        rows_cache[symbol]=rows
        by_t={int(x["t"]):x for x in rows}
        for entry in entries:
            if entry.get("symbol")==symbol:
                _settle(entry,by_t)

        last=rows[-1]
        decision_at_ms=int(last["t"])+HOUR_MS
        previous_decision_at=_last_decision_at(entries,symbol)
        if previous_decision_at is not None and decision_at_ms-previous_decision_at < MIN_CAPTURE_SPACING_MS:
            continue

        result=alpha_analyze(rows,decision_at_ms,btc_rows,symbol)
        ctx=result.get("context") or {}
        a=ctx.get("atr14")
        if a is None:
            continue
        key=f"{symbol}|{decision_at_ms}|{VERSION}|{ALPHA_VERSION}"
        oid=hashlib.sha256(key.encode()).hexdigest()[:24]
        if oid in known:continue

        observation={
            "id":oid,
            "schema":VERSION+"_OBSERVATION",
            "alpha_version":ALPHA_VERSION,
            "symbol":symbol,
            "captured_at":_iso(now_ms),
            "decision_at":_iso(decision_at_ms),
            "decision_at_ms":decision_at_ms,
            "decision_bar_t":int(last["t"]),
            "decision_close":float(last["c"]),
            "capture_lag_minutes":round(max(0,now_ms-decision_at_ms)/60000.0,3),
            "minimum_capture_spacing_minutes":round(MIN_CAPTURE_SPACING_MS/60000.0,3),
            "prediction":result.get("decision","WAIT"),
            "candidate_direction":result.get("candidate_direction"),
            "regime":result.get("regime"),
            "playbook":result.get("playbook"),
            "blockers":list(result.get("blockers") or []),
            "evidence":list(result.get("evidence") or []),
            "evidence_distribution":result.get("evidence_distribution"),
            "probability_calibrated":False,
            "atr14":float(a),
            "outcomes":{},
            "research_only":True,
            "shadow_only":True,
            "paper_only":True,
            "live_execution":False,
            "production_effect":"NONE",
            "can_override_production":False,
            "can_override_final_gate":False,
            "can_change_threshold":False,
            "can_create_trade":False,
        }
        entries.append(observation)
        known.add(oid)
        captured.append(oid)

    for symbol,rows in rows_cache.items():
        by_t={int(x["t"]):x for x in rows}
        for entry in entries:
            if entry.get("symbol")==symbol:
                _settle(entry,by_t)

    ledger.update({
        "generated_at":_iso(now_ms),
        "version":VERSION,
        "alpha_version":ALPHA_VERSION,
        "production_effect":"NONE",
        "research_only":True,
        "shadow_only":True,
        "live_execution":False,
        "can_override_production":False,
        "can_override_final_gate":False,
    })
    lp=Path(ledger_path);lp.parent.mkdir(parents=True,exist_ok=True)
    lp.write_text(json.dumps(ledger,indent=2,sort_keys=True)+"\n")

    metrics={}
    for h in HORIZONS:
        key=f"{h}h";records=[]
        for e in entries:
            o=(e.get("outcomes") or {}).get(key)
            if o:
                records.append({"prediction":e.get("prediction","WAIT"),"actual":o.get("actual")})
        metrics[key]=_metrics(records)

    latest={
        "schema":VERSION+"_LATEST",
        "generated_at":_iso(now_ms),
        "alpha_version":ALPHA_VERSION,
        "state":"FORWARD_SHADOW_COLLECTING",
        "new_observation_ids":captured,
        "entry_count":len(entries),
        "metrics":metrics,
        "minimum_promotion_sample":30,
        "promotion_authority":False,
        "research_only":True,
        "shadow_only":True,
        "live_execution":False,
        "production_effect":"NONE",
        "can_override_production":False,
        "can_override_final_gate":False,
        "can_change_threshold":False,
        "can_create_trade":False,
        "interpretation":"PROSPECTIVE_DIRECTION_EVIDENCE_ONLY_NO_AUTOMATIC_PROMOTION",
    }
    pp=Path(latest_path);pp.parent.mkdir(parents=True,exist_ok=True)
    pp.write_text(json.dumps(latest,indent=2,sort_keys=True)+"\n")
    return latest


if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
