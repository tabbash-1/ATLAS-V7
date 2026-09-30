#!/usr/bin/env python3
"""ADP V2 candidate scan. Development + validation only; test labels stay sealed."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,resample
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
def pct(a,b):return 100*(b/a-1) if a else 0
def feat(h):
 c=[x["c"] for x in h]; e20=ema(c[-80:],20);e50=ema(c[-80:],50);a=atr(h,14); vols=[x["v"] for x in h[-25:-1]]
 return {"m4":pct(c[-5],c[-1]),"m8":pct(c[-9],c[-1]),"m12":pct(c[-13],c[-1]),"acc":pct(c[-5],c[-1])-pct(c[-9],c[-5]),
 "ema":1 if c[-1]>e20>e50 else -1 if c[-1]<e20<e50 else 0,"ext":(c[-1]-e20)/a if a else 0,
 "rv":h[-1]["v"]/statistics.mean(vols) if vols and statistics.mean(vols)>0 else 1,
 "bo":1 if c[-1]>max(x["h"] for x in h[-13:-1]) else -1 if c[-1]<min(x["l"] for x in h[-13:-1]) else 0}
def sign(x):return 1 if x>0 else -1 if x<0 else 0
def pred(f,k):
 s=f["ema"]
 if k=="ema":return s
 if k=="m8":return sign(f["m8"])
 if k=="m12":return sign(f["m12"])
 if k=="ema_m8":return s if s and sign(f["m8"])==s else 0
 if k=="ema_m12":return s if s and sign(f["m12"])==s else 0
 if k=="ema_m8_acc":return s if s and sign(f["m8"])==s and sign(f["acc"])==s else 0
 if k=="ema_m12_acc":return s if s and sign(f["m12"])==s and sign(f["acc"])==s else 0
 if k=="ema_bo":return s if s and f["bo"]==s else 0
 if k=="ema_m8_bo":return s if s and sign(f["m8"])==s and f["bo"]==s else 0
 if k=="ema_m8_rv":return s if s and sign(f["m8"])==s and f["rv"]>=1 else 0
 if k=="ema_m8_acc_rv":return s if s and sign(f["m8"])==s and sign(f["acc"])==s and f["rv"]>=1 else 0
 if k=="bo_rv":return f["bo"] if f["bo"] and f["rv"]>=1 else 0
 return 0
C=["ema","m8","m12","ema_m8","ema_m12","ema_m8_acc","ema_m12_acc","ema_bo","ema_m8_bo","ema_m8_rv","ema_m8_acc_rv","bo_rv"]
def score(rows,k,h):
 x=[r for r in rows if r["h"]==h and (p:=pred(r["f"],k)) and not r["sealed"]]
 n=len(x);ok=sum(pred(r["f"],k)==r["y"] for r in x)
 return {"n":n,"accuracy_pct":round(100*ok/n,2) if n else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=365);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000; raw=[]
 for sym in SYMBOLS:
  d=fetch_1h(sym,a.days,end)
  for i in range(120,len(d)-12,4):
   f=feat(d[:i+1])
   for h in (4,8,12): raw.append({"t":d[i]["t"],"h":h,"f":f,"y":sign(pct(d[i]["c"],d[i+h]["c"]))})
 ts=sorted({r["t"] for r in raw});c1=ts[int(len(ts)*.60)];c2=ts[int(len(ts)*.80)]
 dev=[{**r,"sealed":False} for r in raw if r["t"]<c1]; val=[{**r,"sealed":False} for r in raw if c1<=r["t"]<c2]
 # Deliberately do not calculate or serialize labels/results for t>=c2.
 out={"schema":"ADP_V2_CANDIDATE_SCAN","research_only":True,"production_effect":"NONE","untouched_test_status":"SEALED_NOT_EVALUATED",
 "selection_rule":"highest validation 8h accuracy with n>=300, tie -> higher development 8h accuracy; candidates preregistered in source",
 "candidates":{k:{"development":{str(h):score(dev,k,h) for h in (4,8,12)},"validation":{str(h):score(val,k,h) for h in (4,8,12)}} for k in C}}
 print("ADP_V2_SCAN="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
