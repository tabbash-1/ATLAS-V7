#!/usr/bin/env python3
"""ADP Turning Engine V2: exhaustion -> structure shift -> retest/continuation confirmation."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,rsi
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"];COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def feat(d,i):
 c=[x["c"] for x in d[:i+1]];a=atr(d[max(0,i-40):i+1],14);e20=ema(c[-100:],20);e50=ema(c[-100:],50)
 vs=[x["v"] for x in d[max(0,i-24):i]];rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 return {"m1":pct(c[-2],c[-1]),"m4":pct(c[-5],c[-1]),"m8":pct(c[-9],c[-1]),"rsi":rsi(c[-40:],14),"rv":rv,
 "ext":(c[-1]-e20)/a if a else 0,"spread":(e20-e50)/a if a else 0,"e20":e20,"atr":a}
def exhaust(x,side):
 return (x["rsi"]<=38 and x["ext"]<=-1 and x["m8"]<0) if side==1 else (x["rsi"]>=62 and x["ext"]>=1 and x["m8"]>0)
def candidate(d,i,side):
 # Find exhaustion in last 8h, then demand a break of PREVIOUS 4h structure plus momentum recovery.
 hist=[(j,feat(d,j)) for j in range(max(130,i-8),i)]
 ex=[(j,x) for j,x in hist if exhaust(x,side)]
 if not ex:return False
 j,x0=ex[-1];x=feat(d,i)
 if side==1:
  prior_high=max(z["h"] for z in d[max(j-4,0):j+1])
  shift=d[i]["c"]>prior_high and x["m1"]>0 and x["m4"]>0 and x["rsi"]>x0["rsi"]
  reclaim=d[i]["c"]>x["e20"] or x["ext"]>-0.25
  return shift and reclaim and (x["rv"]>=.9 or x["m4"]>.5)
 prior_low=min(z["l"] for z in d[max(j-4,0):j+1])
 shift=d[i]["c"]<prior_low and x["m1"]<0 and x["m4"]<0 and x["rsi"]<x0["rsi"]
 reclaim=d[i]["c"]<x["e20"] or x["ext"]<.25
 return shift and reclaim and (x["rv"]>=.9 or x["m4"]<-.5)
def st(v):
 if not v:return {"n":0,"avg":None,"pf":None,"wr":None}
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg":round(statistics.mean(v),6),"pf":round(gp/gl,6) if gl else ("INF" if gp else 0),"wr":round(100*sum(x>0 for x in v)/len(v),2)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int,required=True);a=ap.parse_args();rows=[]
 for s in SYMS:
  d=fetch_1h(s,a.days,a.end_ms);last={1:-99,-1:-99}
  for i in range(140,len(d)-13):
   for side in (1,-1):
    if i-last[side]<8 or not candidate(d,i,side):continue
    rows.append({"t":d[i]["t"],"s":s,"side":"UP" if side==1 else "DOWN",
     "r4":side*pct(d[i]["c"],d[i+4]["c"])-COST,"r8":side*pct(d[i]["c"],d[i+8]["c"])-COST,"r12":side*pct(d[i]["c"],d[i+12]["c"])-COST});last[side]=i
 ts=sorted({x["t"] for x in rows});cut=ts[int(len(ts)*.70)] if ts else 0
 out={"schema":"ADP_TURNING_ENGINE_V2","research_only":True,"production_effect":"NONE","cut_t":cut,
 "logic":"causal exhaustion -> prior-structure break -> EMA reclaim/loss -> momentum/volume confirmation","results":{}}
 for h in (4,8,12):
  dev=[x[f"r{h}"] for x in rows if x["t"]<cut];val=[x[f"r{h}"] for x in rows if x["t"]>=cut]
  by={s:st([x[f"r{h}"] for x in rows if x["t"]>=cut and x["s"]==s]) for s in SYMS}
  pos=sum(z["n"]>=10 and z["avg"] is not None and z["avg"]>0 for z in by.values())
  dirs={q:st([x[f"r{h}"] for x in rows if x["t"]>=cut and x["side"]==q]) for q in ("UP","DOWN")}
  out["results"][f"{h}h"]={"dev":st(dev),"validation":st(val),"positive_symbols_min10":pos,"by_direction":dirs,"by_symbol":by}
 Path("status/adp-turning-engine-v2.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print("ADP_TURNING_ENGINE_V2="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
