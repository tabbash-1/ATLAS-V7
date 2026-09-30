#!/usr/bin/env python3
"""ADP V3 frozen contrarian holdout. Rule frozen from V2 dev+validation before test."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
def pct(a,b):return 100*(b/a-1) if a else 0
def sign(x):return 1 if x>0 else -1 if x<0 else 0
def frozen_pred(h):
 c=[x["c"] for x in h];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vols=[x["v"] for x in h[-25:-1]]
 trend=1 if c[-1]>e20>e50 else -1 if c[-1]<e20<e50 else 0
 m8=sign(pct(c[-9],c[-1]));rv=h[-1]["v"]/statistics.mean(vols) if vols and statistics.mean(vols)>0 else 0
 # V3: fade crowded/persistent move only when trend + 8h momentum + >=average volume agree.
 return -trend if trend and m8==trend and rv>=1 else 0
def stats(rows):
 n=len(rows);ok=sum(r["pred"]==r["actual"] for r in rows)
 buy=[r for r in rows if r["pred"]==1];sell=[r for r in rows if r["pred"]==-1]
 def a(x):return {"n":len(x),"accuracy_pct":round(100*sum(r["pred"]==r["actual"] for r in x)/len(x),2) if x else None,"mean_forward_pct":round(sum(r["ret"]*r["pred"] for r in x)/len(x),4) if x else None}
 return {"all":a(rows),"buy":a(buy),"sell":a(sell)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=365);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000; raw=[]
 for sym in SYMBOLS:
  d=fetch_1h(sym,a.days,end)
  for i in range(120,len(d)-12,4):
   p=frozen_pred(d[:i+1])
   for h in (4,8,12):
    ret=pct(d[i]["c"],d[i+h]["c"]);raw.append({"t":d[i]["t"],"symbol":sym,"h":h,"pred":p,"actual":sign(ret),"ret":ret})
 ts=sorted({r["t"] for r in raw});cut=ts[int(len(ts)*.80)]
 test=[r for r in raw if r["t"]>=cut and r["pred"]]
 out={"schema":"ADP_V3_CONTRARIAN_UNTOUCHED_TEST","research_only":True,"production_effect":"NONE",
 "frozen_rule":"inverse EMA20/50 trend when 8h momentum agrees and relative volume >=1.0",
 "selection_provenance":{"v2_development_8h_direct_accuracy_pct":45.23,"v2_validation_8h_direct_accuracy_pct":44.92,
 "implied_inverse_dev_pct":54.77,"implied_inverse_validation_pct":55.08},
 "untouched_test":{str(h):stats([r for r in test if r["h"]==h]) for h in (4,8,12)},
 "by_symbol_8h":{s:stats([r for r in test if r["h"]==8 and r["symbol"]==s])["all"] for s in SYMBOLS}}
 print("ADP_V3_TEST="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
