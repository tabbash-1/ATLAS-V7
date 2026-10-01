#!/usr/bin/env python3
"""ADP Turning Point Lab: discover what changes BEFORE durable direction reversals."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,rsi
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
def pct(a,b):return 100*(b/a-1) if a else 0
def med(v):return round(statistics.median(v),4) if v else None
def features(d,i):
 c=[x["c"] for x in d[:i+1]]; a=atr(d[max(0,i-40):i+1],14); e20=ema(c[-100:],20);e50=ema(c[-100:],50)
 vs=[x["v"] for x in d[max(0,i-24):i]];rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 ap=100*a/c[-1] if a and c[-1] else 0
 return {"m1":pct(c[-2],c[-1]),"m4":pct(c[-5],c[-1]),"m8":pct(c[-9],c[-1]),"m24":pct(c[-25],c[-1]),
 "rsi":rsi(c[-40:],14),"rv":rv,"atr_pct":ap,"ema20_ext_atr":(c[-1]-e20)/a if a else 0,
 "ema_spread_atr":(e20-e50)/a if a else 0}
def turning(d,i,side):
 # Label uses future ONLY to define historical event; features are sampled strictly before i.
 pre=pct(d[i-12]["c"],d[i]["c"]);post=pct(d[i]["c"],d[i+12]["c"])
 if side=="UP": return pre<=-1.0 and post>=1.0 and d[i]["l"]<=min(x["l"] for x in d[i-12:i+13])
 return pre>=1.0 and post<=-1.0 and d[i]["h"]>=max(x["h"] for x in d[i-12:i+13])
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int,required=True);a=ap.parse_args()
 events=[]
 for s in SYMS:
  d=fetch_1h(s,a.days,a.end_ms)
  for i in range(160,len(d)-13):
   for side in ("UP","DOWN"):
    if turning(d,i,side):
     snaps={}
     for lead in (24,12,8,4,2,1,0):
      j=i-lead
      if j>=120:snaps[str(lead)]=features(d,j)
     events.append({"s":s,"t":d[i]["t"],"side":side,"pre12":round(pct(d[i-12]["c"],d[i]["c"]),4),"post12":round(pct(d[i]["c"],d[i+12]["c"]),4),"lead_features":snaps})
 # de-duplicate nearby extrema: keep one event per side/symbol within 12h
 clean=[]
 for e in sorted(events,key=lambda x:(x["s"],x["side"],x["t"])):
  if clean and clean[-1]["s"]==e["s"] and clean[-1]["side"]==e["side"] and e["t"]-clean[-1]["t"]<12*3600000:continue
  clean.append(e)
 agg={}
 for side in ("UP","DOWN"):
  z=[e for e in clean if e["side"]==side];agg[side]={"n":len(z),"by_lead":{}}
  for lead in ("24","12","8","4","2","1","0"):
   rows=[e["lead_features"][lead] for e in z if lead in e["lead_features"]]
   agg[side]["by_lead"][lead]={k:med([r[k] for r in rows if r[k] is not None]) for k in ("m1","m4","m8","m24","rsi","rv","atr_pct","ema20_ext_atr","ema_spread_atr")}
 result={"schema":"ADP_TURNING_POINT_EVENT_STUDY_V1","research_only":True,"production_effect":"NONE",
 "event_definition":"UP: prior12h<=-1%, next12h>=+1%, local 25h low; DOWN inverse. Future used only for labels, never predictor features.",
 "events":len(clean),"aggregate":agg,"sample":clean[:20]}
 Path("status/adp-turning-point-study.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print("ADP_TURNING_POINT_STUDY="+json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
