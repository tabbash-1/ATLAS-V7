#!/usr/bin/env python3
"""Prospective 4H-reversal direction shadow for ATLAS.

Research-only. It records new point-in-time LONG/SHORT/WAIT predictions from the
robust retrospective probe and settles them prospectively at 4H/8H/12H. It
cannot alter Production, Final Trade Gate, thresholds, geometry, or execution.
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

from historical_core_4_12h_replay import fetch_1h, atr

VERSION="ATLAS_REVERSAL4H_FORWARD_SHADOW_V3_FRESH_RUNTIME_CAPTURE"
LEDGER_SCHEMA="ATLAS_REVERSAL4H_FORWARD_LEDGER_V1"
HOUR_MS=60*60*1000
SLOT_MS=4*HOUR_MS
HORIZONS=(4,8,12)
DEADBAND_ATR=0.35
MIN_CAPTURE_SPACING_MS=4*HOUR_MS
SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT")


def _iso(ms):
    return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc).isoformat()


def _closed_rows(rows,now_ms):
    return [x for x in sorted(rows or [],key=lambda z:int(z["t"])) if int(x["t"])+HOUR_MS<=int(now_ms)]


def _last_decision_at(entries,symbol):
    xs=[int(x.get("decision_at_ms") or 0) for x in entries if x.get("symbol")==symbol]
    return max(xs) if xs else None


def reversal4h_prediction(hist):
    if len(hist)<=4:
        return "WAIT",{"reason":"INSUFFICIENT_HISTORY"}
    a=atr(hist,14)
    if not a or a<=0:
        return "WAIT",{"reason":"ATR_UNAVAILABLE"}
    move=float(hist[-1]["c"])-float(hist[-5]["c"])
    move_atr=move/a
    if abs(move)<=DEADBAND_ATR*a:
        return "WAIT",{"reason":"RECENT_4H_MOVE_INSIDE_DEADBAND","atr14":a,"move_4h":move,"move_4h_atr":move_atr}
    recent_side="LONG" if move>0 else "SHORT"
    prediction="SHORT" if recent_side=="LONG" else "LONG"
    return prediction,{
        "reason":"FADE_MEANINGFUL_RECENT_4H_MOVE",
        "atr14":a,
        "move_4h":move,
        "move_4h_atr":move_atr,
        "recent_4h_side":recent_side,
    }


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
    opposite=sum(r["prediction"] in ("LONG","SHORT") and r["actual"] in ("LONG","SHORT") and r["prediction"]!=r["actual"] for r in records)
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
        return {"schema":LEDGER_SCHEMA,"entries":[],"research_only":True,"shadow_only":True,"live_execution":False,"can_override_production":False}
    x=json.loads(p.read_text())
    if x.get("schema")!=LEDGER_SCHEMA:raise RuntimeError("LEDGER_SCHEMA_MISMATCH")
    x.setdefault("entries",[])
    return x


def _settle(entry,rows_by_t):
    outcomes=entry.setdefault("outcomes",{})
    for h in HORIZONS:
        key=str(h)+"h"
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


def run(now_ms=None,fetcher=fetch_1h,ledger_path="status/reversal4h-forward-ledger.json",latest_path="status/reversal4h-forward-shadow-latest.json"):
    now_ms=int(now_ms if now_ms is not None else time.time()*1000)
    ledger=_load(ledger_path)
    entries=ledger["entries"]
    known={x.get("id") for x in entries}
    rows_cache={}
    captured=[]

    for symbol in SYMBOLS:
        rows=_closed_rows(fetcher(symbol,7,now_ms),now_ms)
        if not rows:continue
        rows_cache[symbol]=rows
        by_t={int(x["t"]):x for x in rows}
        for entry in entries:
            if entry.get("symbol")==symbol:
                _settle(entry,by_t)

        # Capture the freshest actually-available closed 1H state at runtime.
        # Do not reconstruct a missed historical slot after scheduler delay.
        decision_hist=rows
        last=decision_hist[-1]
        decision_at_ms=int(last["t"])+HOUR_MS
        previous_decision_at=_last_decision_at(entries,symbol)
        if previous_decision_at is not None and decision_at_ms-previous_decision_at < MIN_CAPTURE_SPACING_MS:
            continue
        capture_lag_ms=max(0,int(now_ms)-decision_at_ms)
        pred,ev=reversal4h_prediction(decision_hist)
        a=ev.get("atr14")
        if a is None:
            # WAIT without an ATR cannot be labeled prospectively with the same policy.
            continue
        key=f"{symbol}|{decision_at_ms}|{VERSION}"
        oid=hashlib.sha256(key.encode()).hexdigest()[:24]
        if oid in known:continue
        row={
            "id":oid,
            "schema":VERSION+"_OBSERVATION",
            "symbol":symbol,
            "captured_at":_iso(now_ms),
            "decision_at":_iso(decision_at_ms),
            "decision_at_ms":decision_at_ms,
            "decision_bar_t":int(last["t"]),
            "decision_close":float(last["c"]),
            "capture_lag_minutes":round(capture_lag_ms/60000.0,3),
            "minimum_capture_spacing_minutes":round(MIN_CAPTURE_SPACING_MS/60000.0,3),
            "prediction":pred,
            "atr14":float(a),
            "evidence":ev,
            "outcomes":{},
            "research_only":True,
            "shadow_only":True,
            "paper_only":True,
            "live_execution":False,
            "can_override_production":False,
            "can_override_final_gate":False,
            "can_change_threshold":False,
        }
        entries.append(row);known.add(oid);captured.append(oid)

    # Settle again in case a newly read symbol provided an already-mature target.
    for symbol,rows in rows_cache.items():
        by_t={int(x["t"]):x for x in rows}
        for entry in entries:
            if entry.get("symbol")==symbol:_settle(entry,by_t)

    ledger["generated_at"]=_iso(now_ms)
    ledger["version"]=VERSION
    ledger["production_effect"]="NONE"
    lp=Path(ledger_path);lp.parent.mkdir(parents=True,exist_ok=True)
    lp.write_text(json.dumps(ledger,indent=2,sort_keys=True)+"\n")

    metrics={}
    for h in HORIZONS:
        key=str(h)+"h";records=[]
        for e in entries:
            o=(e.get("outcomes") or {}).get(key)
            if o:records.append({"prediction":e.get("prediction"),"actual":o.get("actual")})
        metrics[key]=_metrics(records)
    latest={
        "schema":VERSION+"_LATEST",
        "generated_at":_iso(now_ms),
        "state":"FORWARD_SHADOW_COLLECTING",
        "new_observation_ids":captured,
        "entry_count":len(entries),
        "metrics":metrics,
        "research_only":True,
        "shadow_only":True,
        "live_execution":False,
        "production_effect":"NONE",
        "can_override_production":False,
        "can_override_final_gate":False,
        "can_change_threshold":False,
        "interpretation":"PROSPECTIVE_EVIDENCE_ONLY_NO_PROMOTION_AUTHORITY",
    }
    pp=Path(latest_path);pp.parent.mkdir(parents=True,exist_ok=True)
    pp.write_text(json.dumps(latest,indent=2,sort_keys=True)+"\n")
    return latest


if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
