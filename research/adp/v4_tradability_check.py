#!/usr/bin/env python3
"""ADP V4 fixed-8h, non-overlapping-per-symbol, cost-adjusted retrospective tradability check."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
COST_PCT=0.10
def pct(a,b):return 100*(b/a-1) if a else 0
def sig(h):
 c=[x["c"] for x in h];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vols=[x["v"] for x in h[-25:-1]]
 rv=h[-1]["v"]/statistics.mean(vols) if vols and statistics.mean(vols)>0 else 0
 return c[-1]<e20<e50 and pct(c[-9],c[-1])<0 and rv>=1
def summary(x):
 vals=[r["net_pct"] for r in x];gp=sum(v for v in vals if v>0);gl=abs(sum(v for v in vals if v<=0))
 cum=peak=dd=0
 for v in vals:
  cum+=v;peak=max(peak,cum);dd=max(dd,peak-cum)
 return {"n":len(vals),"win_rate_pct":round(100*sum(v>0 for v in vals)/len(vals),2) if vals else None,
 "avg_net_pct":round(statistics.mean(vals),4) if vals else None,"median_net_pct":round(statistics.median(vals),4) if vals else None,
 "net_pct_sum":round(sum(vals),4),"profit_factor":round(gp/gl,4) if gl else None,"max_cumulative_drawdown_pct_points":round(dd,4)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000;tr=[]
 for sym in SYMBOLS:
  d=fetch_1h(sym,a.days,end);i=120
  while i<len(d)-8:
   if sig(d[:i+1]):
    gross=pct(d[i]["c"],d[i+8]["c"]);tr.append({"t":d[i]["t"],"symbol":sym,"net_pct":gross-COST_PCT});i+=8
   else:i+=1
 tr.sort(key=lambda r:r["t"])
 out={"schema":"ADP_V4_TRADABILITY_CHECK","research_only":True,"production_effect":"NONE","horizon_h":8,
 "cost_pct_round_trip":COST_PCT,"overlap_policy":"NO_OVERLAP_PER_SYMBOL_8H","overall":summary(tr),
 "by_symbol":{s:summary([r for r in tr if r["symbol"]==s]) for s in SYMBOLS}}
 print("ADP_V4_TRADABILITY="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
