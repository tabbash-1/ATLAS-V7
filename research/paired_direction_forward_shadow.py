#!/usr/bin/env python3
"""Paired prospective comparison of ATLAS direction challengers.

Runs Reversal4H and Alpha Core V2 on the exact same closed 1H state for every
symbol, freezes both predictions, and settles them at 4H/8H/12H. Research only.
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
from research.reversal4h_forward_shadow import (
    VERSION as REVERSAL_VERSION,
    reversal4h_prediction,
)

VERSION="ATLAS_PAIRED_DIRECTION_FORWARD_SHADOW_V1"
LEDGER_SCHEMA="ATLAS_PAIRED_DIRECTION_FORWARD_LEDGER_V1"
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


def _load(path):
    p=Path(path)
    if not p.exists():
        return {
            "schema":LEDGER_SCHEMA,
            "entries":[],
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
        if key in outcomes:
            continue
        target_t=int(entry["decision_bar_t"])+h*HOUR_MS
        bar=rows_by_t.get(target_t)
        if not bar:
            continue
        actual=_actual(entry["decision_close"],bar["c"],entry["atr14"])
        outcomes[key]={
            "horizon_h":h,
            "target_bar_t":target_t,
            "target_close":float(bar["c"]),
            "actual":actual,
            "reversal_prediction":entry["reversal4h"]["prediction"],
            "alpha_prediction":entry["alpha_core_v2"]["prediction"],
            "reversal_correct":entry["reversal4h"]["prediction"]==actual,
            "alpha_correct":entry["alpha_core_v2"]["prediction"]==actual,
            "settled_at":_iso(target_t+HOUR_MS),
        }


def _model_metrics(entries,horizon,field):
    key=f"{horizon}h"
    rows=[]
    for e in entries:
        o=(e.get("outcomes") or {}).get(key)
        if not o:
            continue
        pred=(e.get(field) or {}).get("prediction","WAIT")
        rows.append((pred,o.get("actual")))
    out={"n":len(rows)}
    if not rows:
        return out
    directional=[x for x in rows if x[0]!="WAIT"]
    correct=sum(p==a for p,a in rows)
    dcorrect=sum(p==a for p,a in directional)
    opposite=sum(p in ("LONG","SHORT") and a in ("LONG","SHORT") and p!=a for p,a in rows)
    out.update({
        "accuracy_pct":round(100*correct/len(rows),3),
        "directional_calls":len(directional),
        "directional_precision_pct":round(100*dcorrect/len(directional),3) if directional else None,
        "opposite_direction_pct_of_calls":round(100*opposite/len(directional),3) if directional else None,
        "wait_rate_pct":round(100*sum(p=="WAIT" for p,_ in rows)/len(rows),3),
    })
    return out


def _head_to_head(entries,horizon):
    key=f"{horizon}h"
    paired=[]
    for e in entries:
        o=(e.get("outcomes") or {}).get(key)
        if not o:
            continue
        rp=(e.get("reversal4h") or {}).get("prediction","WAIT")
        ap=(e.get("alpha_core_v2") or {}).get("prediction","WAIT")
        actual=o.get("actual")
        if rp==ap:
            continue
        paired.append((rp,ap,actual))
    rev_wins=sum(r==a and p!=a for r,p,a in paired)
    alpha_wins=sum(p==a and r!=a for r,p,a in paired)
    both_wrong=sum(r!=a and p!=a for r,p,a in paired)
    return {
        "n_disagreements":len(paired),
        "reversal_only_correct":rev_wins,
        "alpha_only_correct":alpha_wins,
        "both_wrong":both_wrong,
        "reversal_edge":rev_wins-alpha_wins,
    }


def run(now_ms=None,fetcher=fetch_1h,
        ledger_path="status/paired-direction-forward-ledger.json",
        latest_path="status/paired-direction-forward-shadow-latest.json"):
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
        if len(rows)<55:
            continue
        rows_cache[symbol]=rows
        by_t={int(x["t"]):x for x in rows}
        for entry in entries:
            if entry.get("symbol")==symbol:
                _settle(entry,by_t)

        last=rows[-1]
        decision_at_ms=int(last["t"])+HOUR_MS
        previous=_last_decision_at(entries,symbol)
        if previous is not None and decision_at_ms-previous < MIN_CAPTURE_SPACING_MS:
            continue

        rev_pred,rev_ev=reversal4h_prediction(rows)
        a=rev_ev.get("atr14")
        if a is None:
            continue
        alpha=alpha_analyze(rows,decision_at_ms,btc_rows,symbol)
        key=f"{symbol}|{decision_at_ms}|{VERSION}|{REVERSAL_VERSION}|{ALPHA_VERSION}"
        oid=hashlib.sha256(key.encode()).hexdigest()[:24]
        if oid in known:
            continue

        observation={
            "id":oid,
            "schema":VERSION+"_OBSERVATION",
            "symbol":symbol,
            "captured_at":_iso(now_ms),
            "decision_at":_iso(decision_at_ms),
            "decision_at_ms":decision_at_ms,
            "decision_bar_t":int(last["t"]),
            "decision_close":float(last["c"]),
            "capture_lag_minutes":round(max(0,now_ms-decision_at_ms)/60000.0,3),
            "minimum_capture_spacing_minutes":round(MIN_CAPTURE_SPACING_MS/60000.0,3),
            "atr14":float(a),
            "reversal4h":{
                "version":REVERSAL_VERSION,
                "prediction":rev_pred,
                "evidence":rev_ev,
            },
            "alpha_core_v2":{
                "version":ALPHA_VERSION,
                "prediction":alpha.get("decision","WAIT"),
                "candidate_direction":alpha.get("candidate_direction"),
                "regime":alpha.get("regime"),
                "playbook":alpha.get("playbook"),
                "blockers":list(alpha.get("blockers") or []),
                "evidence":list(alpha.get("evidence") or []),
            },
            "outcomes":{},
            "research_only":True,
            "shadow_only":True,
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
        "reversal_version":REVERSAL_VERSION,
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
        metrics[f"{h}h"]={
            "reversal4h":_model_metrics(entries,h,"reversal4h"),
            "alpha_core_v2":_model_metrics(entries,h,"alpha_core_v2"),
            "head_to_head":_head_to_head(entries,h),
        }
    latest={
        "schema":VERSION+"_LATEST",
        "generated_at":_iso(now_ms),
        "state":"FORWARD_SHADOW_COLLECTING",
        "entry_count":len(entries),
        "new_observation_ids":captured,
        "metrics":metrics,
        "minimum_comparison_sample":30,
        "promotion_authority":False,
        "research_only":True,
        "shadow_only":True,
        "live_execution":False,
        "production_effect":"NONE",
        "can_override_production":False,
        "can_override_final_gate":False,
        "can_change_threshold":False,
        "can_create_trade":False,
        "interpretation":"PAIRED_PROSPECTIVE_COMPARISON_ONLY_NO_AUTOMATIC_PROMOTION",
    }
    pp=Path(latest_path);pp.parent.mkdir(parents=True,exist_ok=True)
    pp.write_text(json.dumps(latest,indent=2,sort_keys=True)+"\n")
    return latest


if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
