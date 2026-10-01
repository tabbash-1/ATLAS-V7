#!/usr/bin/env python3
"""ADP V4 external historical replication: frozen LONG-only contrarian rule on older unseen year."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
def pct(a,b):return 100*(b/a-1) if a else 0
def long_signal(h):
 c=[x["c"] for x in h];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vols=[x["v"] for x in h[-25:-1]]
 down=c[-1]<e20<e50;m8=pct(c[-9],c[-1])<0;rv=h[-1]["v"]/statistics.mean(vols) if vols and statistics.mean(vols)>0 else 0
 return down and m8 and rv>=1
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000; boundary=end-365*24*3600*1000; out=[]
 for sym in SYMBOLS:
  d=fetch_1h(sym,a.days,end)
  for i in range(120,len(d)-12,4):
   if not (d[i]["t"]<boundary and long_signal(d[:i+1])):continue
   for h in (4,8,12):out.append({"symbol":sym,"h":h,"ret":pct(d[i]["c"],d[i+h]["c"])})
 def st(x):
  return {"n":len(x),"accuracy_pct":round(100*sum(r["ret"]>0 for r in x)/len(x),2) if x else None,
          "mean_forward_pct":round(sum(r["ret"] for r in x)/len(x),4) if x else None,
          "median_forward_pct":round(statistics.median(r["ret"] for r in x),4) if x else None}
 res={"schema":"ADP_V4_LONG_ONLY_EXTERNAL_REPLICATION","research_only":True,"production_effect":"NONE",
 "period":"OLDER_YEAR_EXCLUDED_FROM_V1_V2_V3_SELECTION","frozen_rule":"BUY when close<EMA20<EMA50, 8h momentum<0, relative volume>=1",
 "overall":{str(h):st([r for r in out if r["h"]==h]) for h in (4,8,12)},
 "by_symbol_8h":{s:st([r for r in out if r["h"]==8 and r["symbol"]==s]) for s in SYMBOLS}}
 print("ADP_V4_REPLICATION="+json.dumps(res,sort_keys=True))
if __name__=="__main__":main()
