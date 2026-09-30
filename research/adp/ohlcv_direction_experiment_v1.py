#!/usr/bin/env python3
"""ADP OHLCV direction experiment V1.

Standalone TradingView-like feature research. Uses closed 1H OHLCV only.
No ATLAS score/gate features. Research-only and cannot mutate Production.
"""
from __future__ import annotations
import argparse,json,statistics,time
from historical_core_4_12h_replay import fetch_1h,ema,atr,resample

SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
H=(4,8,12)

def pct(a,b): return 100*(b/a-1) if a else 0.0
def features(hist):
    c=[x["c"] for x in hist]; r4=resample(hist,4)
    if len(c)<60 or len(r4)<16:return None
    e20=ema(c[-60:],20); e50=ema(c[-60:],50); a=atr(hist,14)
    vols=[x["v"] for x in hist[-25:-1]]
    return {
      "mom_4h":pct(c[-5],c[-1]),"mom_8h":pct(c[-9],c[-1]),"mom_12h":pct(c[-13],c[-1]),
      "accel":pct(c[-5],c[-1])-pct(c[-9],c[-5]),
      "ema_trend":1 if c[-1]>e20>e50 else -1 if c[-1]<e20<e50 else 0,
      "extension_atr":(c[-1]-e20)/a if a else 0,
      "rel_volume":hist[-1]["v"]/statistics.mean(vols) if vols and statistics.mean(vols)>0 else 1,
      "breakout":1 if c[-1]>max(x["h"] for x in hist[-13:-1]) else -1 if c[-1]<min(x["l"] for x in hist[-13:-1]) else 0,
    }
def side(f):
    # Frozen V1 transparent hypothesis: persistent momentum + EMA structure.
    if f["ema_trend"]==1 and f["mom_4h"]>0 and f["mom_8h"]>0:return 1
    if f["ema_trend"]==-1 and f["mom_4h"]<0 and f["mom_8h"]<0:return -1
    return 0
def evaluate(rows):
    out={}
    for h in H:
      x=[r for r in rows if r["horizon_h"]==h and r["pred"]]
      k=sum(r["pred"]==r["actual"] for r in x)
      out[str(h)]={"n":len(x),"accuracy_pct":round(100*k/len(x),2) if x else None,
                   "coverage_pct":None}
    return out
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=365);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
    end=a.end_ms or (int(time.time()*1000)//3600000)*3600000
    rows=[]
    for sym in SYMBOLS:
      data=fetch_1h(sym,a.days,end)
      # sample every 4h; strictly closed bars; leave 12h future.
      for i in range(120,len(data)-12,4):
        f=features(data[:i+1]); s=side(f) if f else 0
        for h in H:
          ret=pct(data[i]["c"],data[i+h]["c"]); actual=1 if ret>0 else -1 if ret<0 else 0
          rows.append({"t":data[i]["t"],"symbol":sym,"horizon_h":h,"pred":s,"actual":actual,"forward_pct":round(ret,6),**(f or {})})
    times=sorted({r["t"] for r in rows}); cut1=times[int(len(times)*.60)];cut2=times[int(len(times)*.80)]
    splits={"development":[r for r in rows if r["t"]<cut1],"validation":[r for r in rows if cut1<=r["t"]<cut2],"untouched_test":[r for r in rows if r["t"]>=cut2]}
    result={"schema":"ADP_OHLCV_DIRECTION_EXPERIMENT_V1","research_only":True,"production_effect":"NONE",
            "symbols":SYMBOLS,"days":a.days,"end_ms":end,"rule":"EMA20/50 trend + 4h/8h momentum persistence",
            "split_policy":"chronological 60/20/20; V1 rule frozen in source before results",
            "splits":{k:evaluate(v) for k,v in splits.items()}}
    print("ADP_RESULT="+json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
