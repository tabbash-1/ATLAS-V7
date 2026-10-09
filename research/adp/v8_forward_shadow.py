#!/usr/bin/env python3
"""ADP V8 forward shadow ledger: frozen V7 rule, append-only, research only."""
from __future__ import annotations
import json,time,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
START_MS=1790799600000
COST=.10
LEDGER=Path("status/adp-v8-forward-ledger.json")
STATUS=Path("status/adp-v8-forward-status.json")
def pct(a,b):return 100*(b/a-1) if a else 0
def signal(d,i):
 c=[x["c"] for x in d[:i+1]];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vs=[x["v"] for x in d[max(0,i-24):i]]
 rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
 return c[-1]>e20>e50 and pct(c[-5],c[-1])>0 and pct(c[-9],c[-1])>0 and rv>=1
def eligible_forward(r):
 """Only freshly captured, already-closed hourly candles count as forward proof.

 Legacy rows are retained in the append-only ledger but excluded from readiness.
 The capture timestamp is written at first insertion, never inferred from outcomes.
 """
 t=r.get("signal_t");captured=r.get("captured_at_ms")
 return (type(t) is int and type(captured) is int
         and 3600000 <= captured-t < 7200000
         and r.get("capture_kind")=="LIVE_HOURLY_CLOSED_CANDLE")

def horizon_stats(verified,h):
 vals=[r["outcomes"][f"{h}h"]["net_pct"] for r in verified if f"{h}h" in r["outcomes"]]
 if not vals:return {"n":0,"net_expectancy_pct":None,"profit_factor":None,"max_arithmetic_drawdown_pctpoints":None}
 gains=sum(v for v in vals if v>0);losses=-sum(v for v in vals if v<0)
 equity=0;peak=0;drawdown=0
 for v in vals:
  equity+=v;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
 return {"n":len(vals),"net_expectancy_pct":round(statistics.mean(vals),6),
         "profit_factor":round(gains/losses,6) if losses else None,
         "max_arithmetic_drawdown_pctpoints":round(drawdown,6)}

def main():
 old=json.loads(LEDGER.read_text()) if LEDGER.exists() else {"schema":"ADP_V8_FORWARD_LEDGER_V1","research_only":True,"production_effect":"NONE","start_ms":START_MS,"signals":[]}
 rows=old["signals"];ids={x["id"] for x in rows};captured_ms=int(time.time()*1000);now=(captured_ms//3600000)*3600000
 for s in SYMBOLS:
  d=fetch_1h(s,30,now);by={x["t"]:i for i,x in enumerate(d)}
  for i in range(120,len(d)-1):
   t=d[i]["t"]
   if t<START_MS or t!=now-3600000:continue
   sid=f"{s}:{t}"
   if sid not in ids and signal(d,i):
    rows.append({"id":sid,"symbol":s,"signal_t":t,"entry":d[i]["c"],"rule":"V7_FROZEN_UP_CONTINUATION","cost_pct":COST,"captured_at_ms":captured_ms,"capture_kind":"LIVE_HOURLY_CLOSED_CANDLE","outcomes":{}});ids.add(sid)
  for r in rows:
   if r["symbol"]!=s:continue
   i=by.get(r["signal_t"])
   if i is None:continue
   for h in (4,8,12):
    k=f"{h}h"
    if k not in r["outcomes"] and i+h<len(d) and d[i+h]["t"]<=now-3600000:
     gross=pct(r["entry"],d[i+h]["c"]);r["outcomes"][k]={"close":d[i+h]["c"],"gross_pct":round(gross,6),"net_pct":round(gross-COST,6)}
 rows.sort(key=lambda x:(x["signal_t"],x["symbol"]));old["signals"]=rows;old["updated_at_ms"]=now
 LEDGER.parent.mkdir(parents=True,exist_ok=True);LEDGER.write_text(json.dumps(old,indent=2,sort_keys=True)+"\n")
 verified=[r for r in rows if eligible_forward(r)]
 matured=[(r,r["outcomes"]["12h"]["net_pct"]) for r in verified if "12h" in r["outcomes"]]
 vals=[v for _,v in matured];gp=sum(v for v in vals if v>0);gl=abs(sum(v for v in vals if v<=0));by={}
 for s in SYMBOLS:
  z=[v for r,v in matured if r["symbol"]==s];by[s]={"n":len(z),"avg_net_pct":round(statistics.mean(z),6) if z else None}
 pos=sum(1 for z in by.values() if z["n"]>=5 and z["avg_net_pct"]>0)
 ready=len(vals)>=500 and statistics.mean(vals)>0 if vals else False
 ready=bool(ready and gl and gp/gl>1 and pos>=7)
 status={"schema":"ADP_V8_FORWARD_STATUS_V2","research_only":True,"production_effect":"NONE","start_ms":START_MS,
 "signals_total":len(rows),"eligible_forward_signals":len(verified),"legacy_unverified_excluded":len(rows)-len(verified),
 "matured_12h":len(vals),"avg_net_pct_12h":round(statistics.mean(vals),6) if vals else None,
 "profit_factor_12h":round(gp/gl,6) if gl else None,"symbols_with_min5_positive":pos,
 "readiness_rule":"VERIFIED_NEW_ONLY: n>=500, avg_net>0, PF>1, >=7 symbols each n>=5 and avg_net>0",
 "ready":ready,"by_symbol_12h":by,"horizons":{f"{h}h":horizon_stats(verified,h) for h in (4,8,12)},
 "drawdown_note":"Arithmetic cumulative percentage-point signal returns, NOT portfolio drawdown"}
 STATUS.write_text(json.dumps(status,indent=2,sort_keys=True)+"\n");print("ADP_V8_STATUS="+json.dumps(status,sort_keys=True))
if __name__=="__main__":main()
