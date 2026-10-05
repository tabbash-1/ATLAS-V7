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
import argparse, json, statistics, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from historical_core_4_12h_replay import fetch_1h, direction, atr, ema, rsi

VERSION="ATLAS_ON_DEMAND_ANALYSIS_BENCHMARK_V6_REVERSAL4H_1H_TRIGGER"
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

def _opposite(side):
    return "SHORT" if side=="LONG" else "LONG" if side=="SHORT" else None


def analyst_stack_v2(hist,decision_time_ms=None,btc_hist=None,symbol=None):
    """Research-only professional top-down analyst challenger.

    The 4H state is the primary swing direction. 12H and completed 1D are veto
    context, 1H is the trigger, BTC is the market anchor for alts, and extreme
    extension/blowoff conditions force WAIT. No outcome-derived thresholds,
    score tuning, or Production mutation is allowed here.
    """
    if not hist:
        return "WAIT"
    as_of=int(decision_time_ms if decision_time_ms is not None else hist[-1]["t"]+HOUR_MS)
    h4=resample_closed(hist,4,as_of)
    h12=resample_closed(hist,12,as_of)
    h24=resample_closed(hist,24,as_of)

    d1=direction(hist)
    d4=direction(h4)
    d12=direction(h12)
    d24=direction(h24)

    if d4 not in ("LONG","SHORT"):
        return "WAIT"
    side=d4
    opp=_opposite(side)

    # Higher timeframes can be aligned or neutral, but may not oppose the 4H thesis.
    if d12==opp or d24==opp:
        return "WAIT"

    # 1H is a trigger, not a competing swing thesis.
    if d1!=side:
        return "WAIT"

    closes=[float(x["c"]) for x in hist]
    a=atr(hist,14)
    e20=ema(closes[-80:],20) if len(closes)>=20 else None
    rs=rsi(closes,14)
    if not a or a<=0 or e20 is None:
        return "WAIT"

    # Do not chase a move that is already >1.5 ATR from its 1H mean.
    extension=abs(closes[-1]-e20)/a
    if extension>1.5:
        return "WAIT"

    # Blowoff/exhaustion veto only; this is intentionally broad, not a tuned RSI band.
    if rs is not None and ((side=="LONG" and rs>=80) or (side=="SHORT" and rs<=20)):
        return "WAIT"

    # Require the most recent completed 1H bar to resume in the thesis direction.
    if len(hist)<2:
        return "WAIT"
    if side=="LONG" and not (hist[-1]["c"]>hist[-2]["c"]):
        return "WAIT"
    if side=="SHORT" and not (hist[-1]["c"]<hist[-2]["c"]):
        return "WAIT"

    # BTC-first for alts: 4H BTC must be directional and non-opposing; 12H/1H BTC
    # may be aligned or neutral, but explicit opposition blocks the alt call.
    sym=str(symbol or "").upper()
    if sym and sym!="BTCUSDT":
        if not btc_hist:
            return "WAIT"
        btc_as_of=[x for x in btc_hist if int(x["t"])<=int(hist[-1]["t"])]
        if len(btc_as_of)<55:
            return "WAIT"
        b1=direction(btc_as_of)
        b4=direction(resample_closed(btc_as_of,4,as_of))
        b12=direction(resample_closed(btc_as_of,12,as_of))
        if b4 not in ("LONG","SHORT"):
            return "WAIT"
        if b4==opp or b12==opp or b1==opp:
            return "WAIT"

    return side


def recent_move_probe(hist,bars,invert=False,deadband_atr=.35):
    """Diagnostic only: asks whether recent realized move tends to persist or reverse."""
    if len(hist)<=bars:
        return "WAIT"
    a=atr(hist,14)
    if not a:
        return "WAIT"
    move=float(hist[-1]["c"])-float(hist[-1-bars]["c"])
    band=float(deadband_atr)*a
    if abs(move)<=band:
        return "WAIT"
    side="LONG" if move>0 else "SHORT"
    return _opposite(side) if invert else side


def momentum_4h_probe(hist,decision_time_ms=None):
    return recent_move_probe(hist,4,False)


def reversal_4h_probe(hist,decision_time_ms=None):
    return recent_move_probe(hist,4,True)


def reversal_4h_1h_trigger_probe(hist,decision_time_ms=None):
    """Diagnostic only: fade a meaningful 4H move only after 1H closes start reversing it."""
    side=recent_move_probe(hist,4,True)
    if side not in ("LONG","SHORT") or len(hist)<2:
        return "WAIT"
    last=float(hist[-1]["c"])
    prev=float(hist[-2]["c"])
    if side=="LONG" and last>prev:
        return "LONG"
    if side=="SHORT" and last<prev:
        return "SHORT"
    return "WAIT"


def momentum_12h_probe(hist,decision_time_ms=None):
    return recent_move_probe(hist,12,False)


def reversal_12h_probe(hist,decision_time_ms=None):
    return recent_move_probe(hist,12,True)


def _recent_move_side(hist,bars,deadband_atr=.35):
    if len(hist)<=bars:
        return None
    a=atr(hist,14)
    if not a:
        return None
    move=float(hist[-1]["c"])-float(hist[-1-bars]["c"])
    band=float(deadband_atr)*a
    if abs(move)<=band:
        return None
    return "LONG" if move>0 else "SHORT"


def thesis12_pullback4_probe(hist,decision_time_ms=None):
    """Diagnostic only: 12H defines thesis; opposing 4H move is treated as a pullback."""
    thesis=_recent_move_side(hist,12)
    pullback=_recent_move_side(hist,4)
    if thesis not in ("LONG","SHORT") or pullback not in ("LONG","SHORT"):
        return "WAIT"
    return thesis if pullback==_opposite(thesis) else "WAIT"


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
      "missed_directional_move_pct":round(100*missed/len(records),3),
      "false_directional_call_pct":round(100*false_action/len(records),3),
      "confusion":cm,
    })
    return out

def temporal_thirds(records):
    """Chronological early/middle/late thirds without mixing the same timestamp across splits."""
    if not records:
        return {"early":metrics([]),"middle":metrics([]),"late":metrics([])}
    times=sorted(set(int(r["t"]) for r in records))
    if len(times)<3:
        return {"early":metrics(records),"middle":metrics([]),"late":metrics([])}
    cut1=times[len(times)//3]
    cut2=times[(2*len(times))//3]
    return {
        "early":metrics([r for r in records if int(r["t"]) < cut1]),
        "middle":metrics([r for r in records if cut1 <= int(r["t"]) < cut2]),
        "late":metrics([r for r in records if int(r["t"]) >= cut2]),
    }


def run(symbol,days,end_ms=None,step=4,rows=None,btc_rows=None):
    rows=rows if rows is not None else fetch_1h(symbol,days,end_ms)
    btc_rows=btc_rows if btc_rows is not None else (rows if symbol=="BTCUSDT" else fetch_1h("BTCUSDT",days,end_ms))
    warm=60*12
    engines={
        "legacy_1h":legacy_1h,
        "htf_consensus":htf_consensus,
        "analyst_stack_v2":analyst_stack_v2,
        "momentum_4h_probe":momentum_4h_probe,
        "reversal_4h_probe":reversal_4h_probe,
        "reversal_4h_1h_trigger_probe":reversal_4h_1h_trigger_probe,
        "momentum_12h_probe":momentum_12h_probe,
        "reversal_12h_probe":reversal_12h_probe,
        "thesis12_pullback4_probe":thesis12_pullback4_probe,
    }
    rec={name:{h:[] for h in HORIZONS} for name in engines}
    for i in range(warm,len(rows)-max(HORIZONS),step):
        hist=rows[:i+1]
        decision_time_ms=int(rows[i]["t"])+HOUR_MS
        preds={
            "legacy_1h":legacy_1h(hist,decision_time_ms),
            "htf_consensus":htf_consensus(hist,decision_time_ms),
            "analyst_stack_v2":analyst_stack_v2(hist,decision_time_ms,btc_rows,symbol),
            "momentum_4h_probe":momentum_4h_probe(hist,decision_time_ms),
            "reversal_4h_probe":reversal_4h_probe(hist,decision_time_ms),
            "reversal_4h_1h_trigger_probe":reversal_4h_1h_trigger_probe(hist,decision_time_ms),
            "momentum_12h_probe":momentum_12h_probe(hist,decision_time_ms),
            "reversal_12h_probe":reversal_12h_probe(hist,decision_time_ms),
            "thesis12_pullback4_probe":thesis12_pullback4_probe(hist,decision_time_ms),
        }
        for h in HORIZONS:
            actual=future_label(rows,i,h)
            if actual is None:continue
            for name,pred in preds.items():
                rec[name][h].append({"t":decision_time_ms,"symbol":symbol,"prediction":pred,"actual":actual})
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=180);ap.add_argument("--end-ms",type=int,default=None);ap.add_argument("--symbols",nargs="*",default=SYMBOLS);ap.add_argument("--step",type=int,default=4);a=ap.parse_args()
    engine_names=("legacy_1h","htf_consensus","analyst_stack_v2","momentum_4h_probe","reversal_4h_probe","reversal_4h_1h_trigger_probe","momentum_12h_probe","reversal_12h_probe","thesis12_pullback4_probe")
    merged={e:{h:[] for h in HORIZONS} for e in engine_names}
    by_symbol={}
    btc_rows=fetch_1h("BTCUSDT",a.days,a.end_ms)
    for s in a.symbols:
        rows=btc_rows if s=="BTCUSDT" else fetch_1h(s,a.days,a.end_ms)
        r=run(s,a.days,a.end_ms,a.step,rows=rows,btc_rows=btc_rows);by_symbol[s]={}
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
        "htf_consensus":"fixed 4H/12H agreement with non-opposing 1H confirmation",
        "analyst_stack_v2":"4H primary thesis; 12H/1D opposition veto; 1H resumption trigger; BTC-first alt veto; 1.5ATR extension and RSI 80/20 blowoff veto",
        "momentum_4h_probe":"diagnostic only: continue the last 4H move when it exceeded 0.35 current 1H ATR",
        "reversal_4h_probe":"diagnostic only: fade the last 4H move when it exceeded 0.35 current 1H ATR",
        "reversal_4h_1h_trigger_probe":"diagnostic only: fade a meaningful 4H move only after the latest completed 1H close starts moving in the reversal direction",
        "momentum_12h_probe":"diagnostic only: continue the last 12H move when it exceeded 0.35 current 1H ATR",
        "reversal_12h_probe":"diagnostic only: fade the last 12H move when it exceeded 0.35 current 1H ATR",
        "thesis12_pullback4_probe":"diagnostic only: use 12H realized direction as thesis and emit it only while the latest 4H realized move is an opposing pullback"
      },
      "overall":{e:{str(h)+"h":metrics(merged[e][h]) for h in HORIZONS} for e in merged},
      "temporal_robustness":{
        e:{str(h)+"h":temporal_thirds(merged[e][h]) for h in HORIZONS}
        for e in ("reversal_4h_probe","reversal_4h_1h_trigger_probe","htf_consensus","legacy_1h")
      },
      "by_symbol":by_symbol}
    print("ATLAS_ON_DEMAND_BENCHMARK="+json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
