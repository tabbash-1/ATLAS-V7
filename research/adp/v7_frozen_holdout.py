#!/usr/bin/env python3
"""ADP V7 frozen untouched recent-year holdout. No tuning."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"];COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def signal(d,i):
 c=[x["c"] for x in d[:i+1]];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vs=[x["v"] for x in d[max(0,i-24):i]]
 rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 return c[-1]>e20>e50 and pct(c[-5],c[-1])>0 and pct(c[-9],c[-1])>0 and rv>=1
def st(v):
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg_net_pct":round(statistics.mean(v),4) if v else None,"median_net_pct":round(statistics.median(v),4) if v else None,
 "win_rate_pct":round(100*sum(x>0 for x in v)/len(v),2) if v else None,"pf":round(gp/gl,4) if gl else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000;cut=end-365*24*3600*1000;allv=[];by={}
 for s in SYMBOLS:
  d=fetch_1h(s,a.days,end);v=[]
  for i in range(120,len(d)-12,4):
   if d[i]["t"]>=cut and signal(d,i):v.append(pct(d[i]["c"],d[i+12]["c"])-COST)
  by[s]=st(v);allv+=v
 positive=sum(1 for z in by.values() if z["avg_net_pct"] is not None and z["avg_net_pct"]>0)
 out={"schema":"ADP_V7_FROZEN_UNTOUCHED_TEST","research_only":True,"production_effect":"NONE","frozen_rule":"LONG close>EMA20>EMA50, mom4>0, mom8>0, relvol>=1; 12h close exit",
 "cost_pct":COST,"overall":st(allv),"by_symbol":by,"positive_symbols":positive,
 "pass_rule":"avg_net>0, PF>1, n>=500, >=7/11 symbols positive","passed":bool(allv and st(allv)["avg_net_pct"]>0 and st(allv)["pf"]>1 and len(allv)>=500 and positive>=7)}
 print("ADP_V7_TEST="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
