#!/usr/bin/env python3
"""ADP V7 economic-edge redesign. Dev/validation only; recent holdout sealed."""
from __future__ import annotations
import argparse,json,statistics,time,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,rsi
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def features(d,i):
 c=[x["c"] for x in d[:i+1]]; vs=[x["v"] for x in d[max(0,i-24):i]]
 e20=ema(c[-80:],20);e50=ema(c[-80:],50);a=atr(d[max(0,i-30):i+1],14)
 rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 return {"m4":pct(c[-5],c[-1]),"m8":pct(c[-9],c[-1]),"m24":pct(c[-25],c[-1]),"trend":1 if c[-1]>e20>e50 else -1 if c[-1]<e20<e50 else 0,
 "rsi":rsi(c[-40:],14),"rv":rv,"ext":(c[-1]-e20)/a if a else 0}
def rule(f,name):
 if name=="oversold_reversal": return 1 if f["trend"]<0 and f["m8"]<0 and f["rsi"]<40 and f["rv"]>=1 else 0
 if name=="deep_extension": return 1 if f["trend"]<0 and f["ext"]<-1 and f["m4"]<0 else 0
 if name=="up_continuation": return 1 if f["trend"]>0 and f["m4"]>0 and f["m8"]>0 and f["rv"]>=1 else 0
 if name=="down_continuation": return -1 if f["trend"]<0 and f["m4"]<0 and f["m8"]<0 and f["rv"]>=1 else 0
 if name=="momentum_accel": return 1 if f["trend"]>0 and f["m4"]>f["m8"]/2 and f["m4"]>0 else -1 if f["trend"]<0 and f["m4"]<f["m8"]/2 and f["m4"]<0 else 0
 if name=="mean_revert_extreme": return -1 if f["ext"]>1.5 and f["rsi"]>65 else 1 if f["ext"]<-1.5 and f["rsi"]<35 else 0
 return 0
def st(rows):
 v=[x["net"] for x in rows];gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg_net_pct":round(statistics.mean(v),4) if v else None,"win_rate_pct":round(100*sum(x>0 for x in v)/len(v),2) if v else None,"pf":round(gp/gl,4) if gl else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000; recent=end-365*24*3600*1000
 market={s:fetch_1h(s,a.days,end) for s in SYMBOLS}; names=["oversold_reversal","deep_extension","up_continuation","down_continuation","momentum_accel","mean_revert_extreme"]
 rows=[]
 for s,d in market.items():
  for i in range(120,len(d)-12,4):
   if d[i]["t"]>=recent:continue
   f=features(d,i)
   for n in names:
    p=rule(f,n)
    if p:
     for h in (4,8,12):rows.append({"t":d[i]["t"],"s":s,"rule":n,"h":h,"net":p*pct(d[i]["c"],d[i+h]["c"])-COST})
 ts=sorted({x["t"] for x in rows});cut=ts[int(len(ts)*.70)] if ts else 0
 result={}
 for n in names:
  for h in (4,8,12):
   dev=[x for x in rows if x["rule"]==n and x["h"]==h and x["t"]<cut];val=[x for x in rows if x["rule"]==n and x["h"]==h and x["t"]>=cut]
   by={s:st([x for x in val if x["s"]==s]) for s in SYMBOLS};pos=sum(1 for z in by.values() if z["avg_net_pct"] is not None and z["avg_net_pct"]>0)
   result[f"{n}_{h}h"]={"dev":st(dev),"validation":st(val),"validation_positive_symbols":pos}
 eligible=[]
 for k,v in result.items():
  d=v["dev"];q=v["validation"]
  if d["n"]>=300 and q["n"]>=150 and d["avg_net_pct"] and q["avg_net_pct"] and d["avg_net_pct"]>0 and q["avg_net_pct"]>0 and d["pf"]>1 and q["pf"]>1 and v["validation_positive_symbols"]>=7:eligible.append((k,v))
 best=max(eligible,key=lambda z:(z[1]["validation"]["pf"],z[1]["validation"]["avg_net_pct"])) if eligible else None
 out={"schema":"ADP_V7_ECONOMIC_EDGE_DEV_VALIDATION","research_only":True,"production_effect":"NONE","cost_pct":COST,
 "data_policy":"OLDER_YEAR_SPLIT_70_30; RECENT_YEAR_SEALED","candidate_count":len(result),
 "promotion_rule":"dev+validation avg>0 PF>1, n>=300/150, validation positive >=7/11 symbols",
 "best":({best[0]:best[1]} if best else None),"candidates":result}
 print("ADP_V7_RESULT="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
