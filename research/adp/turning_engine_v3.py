#!/usr/bin/env python3
"""ADP Turning Engine V3: causal transition sequence, direction-specific."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,rsi
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"];COST=.10
def pct(a,b): return 100*(b/a-1) if a else 0
def F(d,i):
 c=[x["c"] for x in d[:i+1]]; a=atr(d[max(0,i-50):i+1],14); e10=ema(c[-100:],10);e20=ema(c[-100:],20)
 vs=[x["v"] for x in d[max(0,i-24):i]]; rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 return dict(m1=pct(c[-2],c[-1]),m2=pct(c[-3],c[-1]),m4=pct(c[-5],c[-1]),m8=pct(c[-9],c[-1]),
  rsi=rsi(c[-40:],14),rv=rv,atr=a,e10=e10,e20=e20,ext=(c[-1]-e20)/a if a else 0)
def signal(d,i,side):
 # Stage A: locate a genuine stretch/exhaustion episode 3-12h ago.
 cand=[]
 for j in range(max(140,i-12),i-2):
  x=F(d,j)
  ok=(x["rsi"]<=36 and x["ext"]<=-1.15 and x["m8"]<-.5) if side==1 else (x["rsi"]>=66 and x["ext"]>=1.15 and x["m8"]>.5)
  if ok:cand.append((j,x))
 if not cand:return False
 j,x0=cand[-1]; x=F(d,i)
 # Stage B: old trend must fail to extend after exhaustion (observable before current close).
 post=d[j+1:i]
 if not post:return False
 if side==1:
  # no material new low, then higher low + break of post-exhaustion swing high.
  tol=.20*x["atr"]; fail=min(z["l"] for z in post)>=d[j]["l"]-tol
  recent=d[max(j+1,i-3):i]; higher_low=min(z["l"] for z in recent)>d[j]["l"]
  structure=d[i]["c"]>max(z["h"] for z in d[max(j,i-4):i])
  reclaim=d[i]["c"]>x["e10"] and x["m2"]>0 and x["rsi"]>=42
  follow=x["m1"]>0 and (x["rv"]>=.85 or x["m4"]>.35)
  return fail and higher_low and structure and reclaim and follow
 tol=.20*x["atr"]; fail=max(z["h"] for z in post)<=d[j]["h"]+tol
 recent=d[max(j+1,i-3):i]; lower_high=max(z["h"] for z in recent)<d[j]["h"]
 structure=d[i]["c"]<min(z["l"] for z in d[max(j,i-4):i])
 reclaim=d[i]["c"]<x["e10"] and x["m2"]<0 and x["rsi"]<=58
 # downside confirmation deliberately stricter because V2 showed asymmetric false turns
 follow=x["m1"]<0 and x["rv"]>=1.0 and x["m4"]<-.35
 return fail and lower_high and structure and reclaim and follow
def st(v):
 if not v:return {"n":0,"avg":None,"pf":None,"wr":None}
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg":round(statistics.mean(v),6),"pf":round(gp/gl,6) if gl else ("INF" if gp else 0),"wr":round(100*sum(x>0 for x in v)/len(v),2)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int,required=True);a=ap.parse_args();rows=[]
 for s in SYMS:
  d=fetch_1h(s,a.days,a.end_ms);last={1:-99,-1:-99}
  for i in range(150,len(d)-13):
   for side in (1,-1):
    if i-last[side]<12 or not signal(d,i,side):continue
    rows.append({"t":d[i]["t"],"s":s,"side":"UP" if side==1 else "DOWN",
     **{f"r{h}":side*pct(d[i]["c"],d[i+h]["c"])-COST for h in (4,8,12)}});last[side]=i
 ts=sorted({x["t"] for x in rows});cut=ts[int(len(ts)*.70)] if ts else 0
 out={"schema":"ADP_TURNING_ENGINE_V3","research_only":True,"production_effect":"NONE","cut_t":cut,
 "logic":"stretch -> failure-to-continue -> higher-low/lower-high -> structure break -> EMA10 reclaim/loss -> follow-through","results":{}}
 for h in (4,8,12):
  dev=[x[f"r{h}"] for x in rows if x["t"]<cut];val=[x[f"r{h}"] for x in rows if x["t"]>=cut]
  by={s:st([x[f"r{h}"] for x in rows if x["t"]>=cut and x["s"]==s]) for s in SYMS}
  dirs={q:st([x[f"r{h}"] for x in rows if x["t"]>=cut and x["side"]==q]) for q in ("UP","DOWN")}
  out["results"][f"{h}h"]={"dev":st(dev),"validation":st(val),"positive_symbols_min10":sum(z["n"]>=10 and z["avg"] is not None and z["avg"]>0 for z in by.values()),"by_direction":dirs,"by_symbol":by}
 Path("status/adp-turning-engine-v3.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print(json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
