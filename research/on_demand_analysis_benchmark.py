#!/usr/bin/env python3
"""Research-only benchmark for ATLAS' actual product question: analyze now.

At each historical timestamp the benchmark sees only candles available at that
time and must return LONG, SHORT, or WAIT for the 4-12H horizon.  It is not a
trading strategy, does not create orders, and cannot override Production.

V1 deliberately compares two *fixed* analysis hypotheses:
  1. legacy_1h: the simple 1H directional state used by older on-demand logic.
  2. htf_consensus: closed 4H/12H structure with 1H confirmation.

The benchmark labels future direction independently at 4H/8H/12H using a
volatility-scaled deadband. WAIT is therefore measurable rather than treated as
an automatic failure.
"""
from __future__ import annotations
import argparse, json, statistics
from historical_core_4_12h_replay import fetch_1h, direction, atr

VERSION="ATLAS_ON_DEMAND_ANALYSIS_BENCHMARK_V1"
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
HORIZONS=(4,8,12)
HOUR_MS=60*60*1000

def resample_closed(rows,hours,as_of_ms):
    """Aggregate only complete UTC-aligned HTF bars made from contiguous 1H candles."""
    width=hours*HOUR_MS
    buckets={}
    for row in rows:
        start=(int(row["t"])//width)*width
        if start+width>as_of_ms:
            continue
        buckets.setdefault(start,[]).append(row)
    out=[]
    for start,items in sorted(buckets.items()):
        items=sorted(items,key=lambda x:int(x["t"]))
        expected=[start+i*HOUR_MS for i in range(hours)]
        if len(items)!=hours or [int(x["t"]) for x in items]!=expected:
            continue
        out.append({"t":start,"o":items[0]["o"],"h":max(x["h"] for x in items),
                    "l":min(x["l"] for x in items),"c":items[-1]["c"],
                    "v":sum(x["v"] for x in items)})
    return out

def legacy_1h(hist,decision_time_ms=None):
    d=direction(hist)
    return d if d in ("LONG","SHORT") else "WAIT"

def htf_consensus(hist,decision_time_ms=None):
    if not hist:
        return "WAIT"
    as_of=int(decision_time_ms if decision_time_ms is not None else hist[-1]["t"]+HOUR_MS)
    d1=direction(hist)
    d4=direction(resample_closed(hist,4,as_of))
    d12=direction(resample_closed(hist,12,as_of))
    if d4 in ("LONG","SHORT") and d4==d12:
        return d4 if d1 in (None,d4) else "WAIT"
    return "WAIT"

def future_label(rows,i,h,deadband_atr=.35):
    a=atr(rows[:i+1],14)
    if not a or i+h>=len(rows): return None
    move=rows[i+h]["c"]-rows[i]["c"]
    band=deadband_atr*a
    if move>band:return "LONG"
    if move<-band:return "SHORT"
    return "WAIT"

def metrics(records):
    out={"n":len(records)}
    if not records:return out
    labels=("LONG","SHORT","WAIT")
    cm={p:{a:0 for a in labels} for p in labels}
    for r in records:cm[r["prediction"]][r["actual"]]+=1
    correct=sum(cm[x][x] for x in labels)
    directional=[r for r in records if r["prediction"]!="WAIT"]
    dcorrect=sum(r["prediction"]==r["actual"] for r in directional)
    missed=sum(r["prediction"]=="WAIT" and r["actual"]!="WAIT" for r in records)
    false_action=sum(r["prediction"]!="WAIT" and r["actual"]=="WAIT" for r in records)
    out.update({
      "accuracy_pct":round(100*correct/len(records),3),
      "directional_calls":len(directional),
      "directional_precision_pct":round(100*dcorrect/len(directional),3) if directional else None,
      "wait_rate_pct":round(100*sum(r["prediction"]=="WAIT" for r in records)/len(records),3),
      "missed_directional_move_pct":round(100*missed/len(records),3),
      "false_directional_call_pct":round(100*false_action/len(records),3),
      "confusion":cm,
    })
    return out

def run(symbol,days,end_ms=None,step=4,rows=None):
    rows=rows if rows is not None else fetch_1h(symbol,days,end_ms)
    warm=60*12
    engines={"legacy_1h":legacy_1h,"htf_consensus":htf_consensus}
    rec={name:{h:[] for h in HORIZONS} for name in engines}
    for i in range(warm,len(rows)-max(HORIZONS),step):
        hist=rows[:i+1]
        decision_time_ms=int(rows[i]["t"])+HOUR_MS
        preds={name:fn(hist,decision_time_ms) for name,fn in engines.items()}
        for h in HORIZONS:
            actual=future_label(rows,i,h)
            if actual is None:continue
            for name,pred in preds.items():
                rec[name][h].append({"t":decision_time_ms,"symbol":symbol,"prediction":pred,"actual":actual})
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=180);ap.add_argument("--end-ms",type=int,default=None);ap.add_argument("--symbols",nargs="*",default=SYMBOLS);ap.add_argument("--step",type=int,default=4);a=ap.parse_args()
    merged={e:{h:[] for h in HORIZONS} for e in ("legacy_1h","htf_consensus")}
    by_symbol={}
    for s in a.symbols:
        rows=fetch_1h(s,a.days,a.end_ms)
        r=run(s,a.days,a.end_ms,a.step,rows=rows);by_symbol[s]={}
        for e in merged:
            by_symbol[s][e]={}
            for h in HORIZONS:
                merged[e][h]+=r[e][h]
                by_symbol[s][e][str(h)+"h"]=metrics(r[e][h])
    result={"schema":VERSION,"research_only":True,"production_effect":"NONE","can_override_production":False,
      "purpose":"MEASURE_ON_DEMAND_LONG_SHORT_WAIT_ANALYSIS_NOT_TRADE_DISCOVERY",
      "days":a.days,"step_h":a.step,"horizons_h":list(HORIZONS),
      "label_policy":"future close move vs current close; WAIT when abs(move)<=0.35*current 1H ATR",
      "decision_clock":"Closed 1H decisions; only complete contiguous UTC-aligned 4H and 12H candles are eligible.",
      "engines":{
        "legacy_1h":"fixed simple 1H state baseline",
        "htf_consensus":"fixed 4H/12H agreement with non-opposing 1H confirmation"
      },
      "overall":{e:{str(h)+"h":metrics(merged[e][h]) for h in HORIZONS} for e in merged},
      "by_symbol":by_symbol}
    print("ATLAS_ON_DEMAND_BENCHMARK="+json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
