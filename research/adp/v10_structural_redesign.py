#!/usr/bin/env python3
"""ADP V10 structural redesign: volatility-normalized momentum + BTC market regime."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema,atr,rsi
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"];COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def st(v):
 if not v:return {"n":0,"avg":None,"pf":None}
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"avg":round(statistics.mean(v),6),"pf":round(gp/gl,6) if gl else ("INF" if gp else 0)}
def f(d,i):
 c=[x["c"] for x in d[:i+1]];e20=ema(c[-100:],20);e50=ema(c[-100:],50);a=atr(d[max(0,i-40):i+1],14)
 vs=[x["v"] for x in d[max(0,i-24):i]];rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 ap=100*a/c[-1] if a and c[-1] else 0
 return {"up":c[-1]>e20>e50,"m4n":pct(c[-5],c[-1])/ap if ap else 0,"m8n":pct(c[-9],c[-1])/ap if ap else 0,
 "m24n":pct(c[-25],c[-1])/ap if ap else 0,"rv":rv,"rsi":rsi(c[-40:],14),"extn":(c[-1]-e20)/a if a else 99}
RULES={
"NORM_A":lambda x,b:x["up"] and x["m4n"]>0.25 and x["m8n"]>0.5 and x["m24n"]>0 and x["rv"]>=1 and b["up"],
"NORM_B":lambda x,b:x["up"] and x["m4n"]>0.15 and x["m8n"]>0.35 and x["m24n"]>0 and x["rv"]>=1 and x["extn"]<=1.5 and b["up"],
"NORM_C":lambda x,b:x["up"] and x["m4n"]>0.25 and x["m8n"]>0.5 and x["rv"]>=1 and 50<=x["rsi"]<=72 and b["up"] and b["m8n"]>0,
"NORM_D":lambda x,b:x["up"] and x["m4n"]>0.10 and x["m8n"]>0.30 and x["m24n"]>0 and x["extn"]<=1.25 and b["up"] and b["m24n"]>0,
}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int,required=True);a=ap.parse_args()
 market={s:fetch_1h(s,a.days,a.end_ms) for s in SYMS}; btc={x["t"]:i for i,x in enumerate(market["BTCUSDT"])}; rows=[]
 for s,d in market.items():
  for i in range(120,len(d)-12,4):
   bi=btc.get(d[i]["t"])
   if bi is None or bi<120:continue
   x=f(d,i);b=f(market["BTCUSDT"],bi)
   for n,r in RULES.items():
    if r(x,b):rows.append({"t":d[i]["t"],"s":s,"rule":n,"net":pct(d[i]["c"],d[i+12]["c"])-COST})
 ts=sorted({x["t"] for x in rows});cut=ts[int(len(ts)*.70)] if ts else 0;out={}
 for n in RULES:
  dev=[x for x in rows if x["rule"]==n and x["t"]<cut];val=[x for x in rows if x["rule"]==n and x["t"]>=cut]
  ds=st([x["net"] for x in dev]);vs=st([x["net"] for x in val]);by={s:st([x["net"] for x in val if x["s"]==s]) for s in SYMS}
  pos=sum(z["n"]>=10 and z["avg"] is not None and z["avg"]>0 for z in by.values())
  passed=ds["n"]>=500 and vs["n"]>=200 and ds["avg"] and ds["avg"]>0 and vs["avg"] and vs["avg"]>0 and ds["pf"]>1 and vs["pf"]>1 and pos>=7
  out[n]={"dev":ds,"validation":vs,"positive_symbols_min10":pos,"by_symbol":by,"passes":bool(passed)}
 result={"schema":"ADP_V10_STRUCTURAL_DEV_VALIDATION_V1","research_only":True,"production_effect":"NONE","cost_pct":COST,
 "design":"volatility-normalized momentum plus BTC regime; same rule all symbols; chronological 70/30; no symbol exclusions",
 "gate":"dev n>=500,val n>=200,avg>0,PF>1 both,>=7/11 positive symbols min10","cut_t":cut,"candidates":out}
 Path("status/adp-v10-dev-validation.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print("ADP_V10="+json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
