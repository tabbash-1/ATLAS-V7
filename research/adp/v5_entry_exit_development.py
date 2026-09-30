#!/usr/bin/env python3
"""ADP V5 entry/exit development. Selection uses older year only; recent year stays sealed."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def setup(h):
 c=[x["c"] for x in h];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vs=[x["v"] for x in h[-25:-1]]
 rv=h[-1]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 0
 return c[-1]<e20<e50 and pct(c[-9],c[-1])<0 and rv>=1
def exit_ret(d,i,hold,tp,sl):
 entry=d[i]["c"]; last=min(i+hold,len(d)-1)
 for j in range(i+1,last+1):
  hi=pct(entry,d[j]["h"]);lo=pct(entry,d[j]["l"])
  hit_tp=hi>=tp;hit_sl=lo<=-sl
  if hit_tp and hit_sl:return -sl-COST,j # conservative same-bar ambiguity
  if hit_sl:return -sl-COST,j
  if hit_tp:return tp-COST,j
 return pct(entry,d[last]["c"])-COST,last
def stats(vals):
 gp=sum(v for v in vals if v>0);gl=abs(sum(v for v in vals if v<=0))
 return {"n":len(vals),"win_rate_pct":round(100*sum(v>0 for v in vals)/len(vals),2) if vals else None,
 "avg_net_pct":round(statistics.mean(vals),4) if vals else None,"median_net_pct":round(statistics.median(vals),4) if vals else None,
 "profit_factor":round(gp/gl,4) if gl else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000;cut=end-365*24*3600*1000
 configs=[(h,tp,sl) for h in (4,8,12) for tp,sl in ((.5,.5),(.75,.5),(1,.5),(1,.75),(1,1),(1.5,.75),(1.5,1),(2,1))]
 out={}
 for cfg in configs:
  hold,tp,sl=cfg;vals=[]
  for sym in SYMBOLS:
   d=fetch_1h(sym,a.days,end);i=120
   while i<len(d)-12 and d[i]["t"]<cut:
    if setup(d[:i+1]):
     r,j=exit_ret(d,i,hold,tp,sl);vals.append(r);i=max(i+1,j)
    else:i+=1
  out[f"h{hold}_tp{tp}_sl{sl}"]=stats(vals)
 eligible=[(k,v) for k,v in out.items() if v["n"]>=1000 and v["profit_factor"] is not None]
 best=max(eligible,key=lambda kv:(kv[1]["profit_factor"],kv[1]["avg_net_pct"])) if eligible else (None,None)
 print("ADP_V5_DEV="+json.dumps({"schema":"ADP_V5_ENTRY_EXIT_DEVELOPMENT","research_only":True,"production_effect":"NONE",
 "data_policy":"OLDER_YEAR_ONLY; RECENT_YEAR_SEALED","cost_pct_round_trip":COST,"same_bar_policy":"STOP_FIRST_CONSERVATIVE",
 "candidates":out,"selected_by":"max profit factor among n>=1000; tie avg net","best":{best[0]:best[1]} if best[0] else None},sort_keys=True))
if __name__=="__main__":main()
