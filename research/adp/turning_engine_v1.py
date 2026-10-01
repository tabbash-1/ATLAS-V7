#!/usr/bin/env python3
"""ADP Turning Engine V1: causal reversal state machine derived from event-study precursors."""
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
 "ext":(c[-1]-e20)/a if a else 0,"spread":(e20-e50)/a if a else 0}
def state(d,i):
 x=feat(d,i)
 up_ex=x["rsi"]<=38 and x["ext"]<=-1.0 and x["m8"]<0
 dn_ex=x["rsi"]>=62 and x["ext"]>=1.0 and x["m8"]>0
 # Confirmation must be observable now: momentum inflection plus volume/price reclaim.
 if up_ex:
  return "UP_EXHAUSTION"
 if dn_ex:
  return "DOWN_EXHAUSTION"
 # recent exhaustion in prior 4h, followed by causal inflection
 prev=[feat(d,j) for j in range(max(120,i-4),i)]
 had_up=any(z["rsi"]<=40 and z["ext"]<=-0.8 and z["m8"]<0 for z in prev)
 had_dn=any(z["rsi"]>=60 and z["ext"]>=0.8 and z["m8"]>0 for z in prev)
 if had_up and x["m1"]>0 and x["m4"]>prev[-1]["m4"] and (x["rv"]>=1 or x["rsi"]>prev[-1]["rsi"]):return "UP_TURN_CONFIRMED"
 if had_dn and x["m1"]<0 and x["m4"]<prev[-1]["m4"] and (x["rv"]>=1 or x["rsi"]<prev[-1]["rsi"]):return "DOWN_TURN_CONFIRMED"
 return "NONE"
def st(v):
 if not v:return {"n":0,"avg":None,"pf":None,"wr":None}
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg":round(statistics.mean(v),6),"pf":round(gp/gl,6) if gl else ("INF" if gp else 0),"wr":round(100*sum(x>0 for x in v)/len(v),2)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int,required=True);a=ap.parse_args()
 rows=[]
 for s in SYMS:
  d=fetch_1h(s,a.days,a.end_ms);last=-99
  for i in range(130,len(d)-13):
   q=state(d,i)
   if q not in ("UP_TURN_CONFIRMED","DOWN_TURN_CONFIRMED") or i-last<8:continue
   side=1 if q.startswith("UP") else -1
   rows.append({"t":d[i]["t"],"s":s,"state":q,
    "r4":side*pct(d[i]["c"],d[i+4]["c"])-COST,"r8":side*pct(d[i]["c"],d[i+8]["c"])-COST,"r12":side*pct(d[i]["c"],d[i+12]["c"])-COST});last=i
 ts=sorted({x["t"] for x in rows});cut=ts[int(len(ts)*.70)] if ts else 0
 out={"schema":"ADP_TURNING_ENGINE_V1","research_only":True,"production_effect":"NONE","cut_t":cut,
 "logic":"causal exhaustion then observable momentum inflection; no future features","results":{}}
 for h in (4,8,12):
  dev=[x[f"r{h}"] for x in rows if x["t"]<cut];val=[x[f"r{h}"] for x in rows if x["t"]>=cut]
  by={s:st([x[f"r{h}"] for x in rows if x["t"]>=cut and x["s"]==s]) for s in SYMS}
  pos=sum(z["n"]>=10 and z["avg"] is not None and z["avg"]>0 for z in by.values())
  out["results"][f"{h}h"]={"dev":st(dev),"validation":st(val),"positive_symbols_min10":pos,"by_symbol":by}
 Path("status/adp-turning-engine-v1.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print("ADP_TURNING_ENGINE="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
