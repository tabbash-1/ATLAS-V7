#!/usr/bin/env python3
"""ADP V8 frozen-rule historical point-in-time replay. Research only."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema

SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
FORWARD_START_MS=1790799600000
COST=.10

def pct(a,b): return 100*(b/a-1) if a else 0

def signal(d,i):
    c=[x["c"] for x in d[:i+1]]
    e20=ema(c[-80:],20); e50=ema(c[-80:],50)
    vs=[x["v"] for x in d[max(0,i-24):i]]
    rv=d[i]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 1
    return c[-1]>e20>e50 and pct(c[-5],c[-1])>0 and pct(c[-9],c[-1])>0 and rv>=1

def summarize(vals):
    if not vals:return {"n":0,"win_rate_pct":None,"avg_net_pct":None,"profit_factor":None,"net_sum_pct":0}
    gp=sum(v for v in vals if v>0); gl=abs(sum(v for v in vals if v<=0))
    return {"n":len(vals),"win_rate_pct":round(100*sum(v>0 for v in vals)/len(vals),2),
            "avg_net_pct":round(statistics.mean(vals),6),
            "profit_factor":round(gp/gl,6) if gl else ("INF" if gp else 0),
            "net_sum_pct":round(sum(vals),6)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--days",type=int,default=365); a=ap.parse_args()
    end_ms=FORWARD_START_MS-3600000
    horizons=(4,8,12); records=[]
    for s in SYMBOLS:
        d=fetch_1h(s,a.days,end_ms)
        for i in range(120,len(d)-12):
            if not signal(d,i): continue
            rec={"symbol":s,"signal_t":d[i]["t"],"entry":d[i]["c"],"outcomes":{}}
            for h in horizons:
                gross=pct(d[i]["c"],d[i+h]["c"]); rec["outcomes"][f"{h}h"]=round(gross-COST,6)
            records.append(rec)
    result={"schema":"ADP_V8_HISTORICAL_REPLAY_V1","research_only":True,"production_effect":"NONE",
            "rule":"V7_FROZEN_UP_CONTINUATION","point_in_time":True,"lookahead_in_signal":False,
            "cost_pct":COST,"days":a.days,"end_ms":end_ms,"forward_start_ms":FORWARD_START_MS,
            "signals_total":len(records),"by_horizon":{},"by_symbol":{}}
    for h in horizons:
        vals=[r["outcomes"][f"{h}h"] for r in records]; result["by_horizon"][f"{h}h"]=summarize(vals)
    for s in SYMBOLS:
        z=[r for r in records if r["symbol"]==s]
        result["by_symbol"][s]={f"{h}h":summarize([r["outcomes"][f"{h}h"] for r in z]) for h in horizons}
    out=Path("status/adp-v8-historical-backtest.json"); out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("ADP_V8_HISTORICAL_BACKTEST="+json.dumps(result,sort_keys=True))

if __name__=="__main__": main()
