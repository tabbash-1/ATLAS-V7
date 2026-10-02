"""Historical exam adapter for the ATLAS Profitability 1-9 pipeline.

Consumes only point-in-time replay trades already constructed without future
candles. Future outcomes are used only after a candidate decision is frozen.
"""
from __future__ import annotations
import json, statistics
import historical_core_4_12h_replay as core
from profitability_market_radar import build as radar_build
from profitability_ev_plan_replay import replay_kpis

VERSION="ATLAS_PROFITABILITY_PIPELINE_HISTORICAL_EXAM_V1"

def _dd_r(rs):
    eq=peak=0.0; dd=0.0
    for r in rs:
        eq+=r; peak=max(peak,eq); dd=max(dd,peak-eq)
    return round(dd,4)

def exam_symbol(symbol,days,end_ms):
    rows=core.fetch_1h(symbol,days,end_ms); warm=60*12
    frozen=[]; i=warm
    while i<len(rows)-12:
        decision_t=rows[i]["t"]
        sig=core.signal(rows[:i+1])  # hard temporal boundary
        state="ACTIONABLE" if sig.get("ready") else ("ARMED" if sig.get("side") and (sig.get("score") or 0)>=60 else "NO_SETUP")
        rr=2.0 if sig.get("ready") else None
        ranked=radar_build([{"symbol":symbol,"direction":sig.get("side"),"opportunity_state":state,
          "score":sig.get("score") or 0,"threshold":68,"rr_tp2":rr,
          "geometry_valid":bool(sig.get("ready")),"execution_ready":bool(sig.get("ready")),
          "action":sig.get("side") if sig.get("ready") else "WAIT"}])["ranked_universe"][0]
        row={"decision_t":decision_t,"symbol":symbol,"state":state,"radar_score":ranked["radar_score"],
             "side":sig.get("side"),"ready":bool(sig.get("ready")),"score":sig.get("score")}
        if sig.get("ready"):
            r,out=core.settle(sig,rows[i+1:i+13])  # outcomes accessed only after freeze
            row.update({"settled":True,"r":round(r,4),"outcome":out,"tradeable_opportunity":True,
                        "atlas_captured":True,"detection_latency_min":0,"entry_efficiency":1.0})
            i+=12
        else:
            row.update({"settled":False,"tradeable_opportunity":False,"atlas_captured":False})
            i+=4
        frozen.append(row)
    return frozen

def summarize(rows):
    trades=[x for x in rows if x.get("settled")]; rs=[x["r"] for x in trades]
    wins=[r for r in rs if r>0]; losses=[r for r in rs if r<=0]
    gp=sum(wins); gl=abs(sum(losses))
    return {"trades":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,
      "win_rate_pct":round(100*len(wins)/len(rs),2) if rs else None,
      "profit_factor_r":round(gp/gl,4) if gl else None,"max_drawdown_r":_dd_r(rs),
      "replay_kpis":replay_kpis(trades)}

def run(symbols,days,end_ms):
    allrows=[]; by={}
    for s in symbols:
        rows=exam_symbol(s,days,end_ms); allrows+=rows; by[s]=summarize(rows)
    return {"schema":VERSION,"symbols":symbols,"days":days,"end_ms":end_ms,"overall":summarize(allrows),
      "by_symbol":by,"safety":{"research_only":True,"forward_proof_equivalent":False,
      "future_candles_in_signal":False,"production_impact":"NONE","threshold":68}}

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--days",type=int,default=180); ap.add_argument("--end-ms",type=int,required=True)
    ap.add_argument("--symbols",nargs="*",default=core.SYMBOLS); a=ap.parse_args()
    print("ATLAS_PROFITABILITY_EXAM="+json.dumps(run(a.symbols,a.days,a.end_ms),sort_keys=True))
