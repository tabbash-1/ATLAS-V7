#!/usr/bin/env python3
"""ADP V9 preregistered redesign: cross-symbol regime/quality filters, chronological dev/validation."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,rsi
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def feat(d,i):
 c=[x["c"] for x in d[:i+1]]; e20=ema(c[-80:],20);e50=ema(c[-80:],50);a=atr(d[max(0,i-30):i+1],14)
 vs=[x["v"] for x in d[max(0,i-24):i]];rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 return {"trend":c[-1]>e20>e50,"m4":pct(c[-5],c[-1]),"m8":pct(c[-9],c[-1]),"m24":pct(c[-25],c[-1]),
 "rv":rv,"rsi":rsi(c[-40:],14),"ext":(c[-1]-e20)/a if a else 99,"sep":(e20-e50)/a if a else 0}
def base(f):return f["trend"] and f["m4"]>0 and f["m8"]>0 and f["rv"]>=1
RULES={
"BASE":lambda f:base(f),
"QUALITY_A":lambda f:base(f) and 50<=f["rsi"]<=68 and 0<=f["ext"]<=1.0 and f["sep"]>=0.15,
"QUALITY_B":lambda f:base(f) and 52<=f["rsi"]<=70 and 0<=f["ext"]<=1.5 and f["m24"]>0,
"QUALITY_C":lambda f:base(f) and f["m24"]>0 and f["m4"]>=0.25*f["m8"] and f["ext"]<=1.0,
"QUALITY_D":lambda f:base(f) and 50<=f["rsi"]<=72 and f["sep"]>=0.25 and f["m24"]>0 and f["ext"]<=1.25,
}
def st(v):
 if not v:return {"n":0,"avg":None,"pf":None,"wr":None}
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg":round(statistics.mean(v),6),"pf":round(gp/gl,6) if gl else ("INF" if gp else 0),"wr":round(100*sum(x>0 for x in v)/len(v),2)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int,required=True);a=ap.parse_args()
 rows=[]
 for s in SYMBOLS:
  d=fetch_1h(s,a.days,a.end_ms)
  for i in range(120,len(d)-12,4):
   f=feat(d,i)
   for name,rule in RULES.items():
    if rule(f):rows.append({"t":d[i]["t"],"s":s,"rule":name,"net":pct(d[i]["c"],d[i+12]["c"])-COST})
 times=sorted({x["t"] for x in rows});cut=times[int(len(times)*.70)] if times else 0
 out={}
 for name in RULES:
  dev=[x for x in rows if x["rule"]==name and x["t"]<cut];val=[x for x in rows if x["rule"]==name and x["t"]>=cut]
  by={s:st([x["net"] for x in val if x["s"]==s]) for s in SYMBOLS}
  pos=sum(1 for z in by.values() if z["n"]>=10 and z["avg"] is not None and z["avg"]>0)
  ds=st([x["net"] for x in dev]);vs=st([x["net"] for x in val])
  passes=ds["n"]>=500 and vs["n"]>=200 and ds["avg"] and ds["avg"]>0 and vs["avg"] and vs["avg"]>0 and ds["pf"]>1 and vs["pf"]>1 and pos>=7
  out[name]={"dev":ds,"validation":vs,"validation_positive_symbols_min10":pos,"by_symbol_validation":by,"passes":bool(passes)}
 result={"schema":"ADP_V9_PREREGISTERED_DEV_VALIDATION_V1","research_only":True,"production_effect":"NONE","cost_pct":COST,
 "design":"same rule across all symbols; no symbol exclusion; 4h sampling; 12h outcome; chronological 70/30",
 "gate":"dev n>=500, validation n>=200, avg>0 and PF>1 both, >=7/11 validation symbols n>=10 positive","cut_t":cut,"candidates":out}
 Path("status/adp-v9-dev-validation.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print("ADP_V9="+json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
