"""Settle prospective Regime Transition Challenger observations.

Research-only. Uses public 5m candles after the frozen decision timestamp and
never feeds outcomes back into Production. Conservative both-hit rule: stop first.
"""
from __future__ import annotations
import datetime as dt, json, math
from pathlib import Path
from offline_production_path_settlement import market_klines

SCHEMA="ATLAS_REGIME_TRANSITION_OUTCOMES_V1"
COST_BPS=10
HORIZONS=(4,8,12)

def _f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def _time(v): return dt.datetime.fromisoformat(str(v).replace("Z","+00:00"))

def _price_from_obs(obs):
    e=obs.get("frozen_evidence") or {}
    for k in ("entry","market_reference_price","price"):
        x=_f(e.get(k) or obs.get(k))
        if x and x>0:return x
    return None

def _geometry(obs):
    e=obs.get("frozen_evidence") or {}; direction=obs.get("candidate_direction")
    entry=_price_from_obs(obs); stop=_f(e.get("stop_loss")); tp=_f(e.get("tp2"))
    if not entry:return None
    if not stop or not tp:
        # Do not synthesize geometry retrospectively.
        return None
    valid=(direction=="LONG" and stop<entry<tp) or (direction=="SHORT" and tp<entry<stop)
    return {"entry":entry,"stop":stop,"tp2":tp} if valid else None

def settle_one(obs,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    out={"observation_id":obs.get("observation_id"),"decision_id":obs.get("decision_id"),
         "symbol":obs.get("symbol"),"captured_at":obs.get("captured_at"),
         "candidate_direction":obs.get("candidate_direction"),"challenger_decision":(obs.get("challenger") or {}).get("decision"),
         "research_only":True,"live_execution":False,"can_override_production":False,
         "modeled_round_trip_cost_bps":COST_BPS,"horizons":{}}
    if not (obs.get("challenger") or {}).get("eligible"):
        out["status"]="INELIGIBLE"; return out
    g=_geometry(obs)
    if not g:
        out["status"]="NO_FROZEN_GEOMETRY"; return out
    start=int(_time(obs["captured_at"]).timestamp()*1000)
    if int(now.timestamp()*1000)<start+4*3600_000:
        out["status"]="OPEN"; return out
    end=min(int(now.timestamp()*1000),start+12*3600_000)
    try:candles,provider=market_klines(obs["symbol"],"5",start,end)
    except Exception as exc:
        out.update({"status":"MARKET_DATA_ERROR","error":str(exc)[:300]}); return out
    if not candles:
        out.update({"status":"MARKET_DATA_ERROR","error":"no_candles"}); return out
    side=obs["candidate_direction"]; risk=abs(g["entry"]-g["stop"])
    cost_r=(g["entry"]*(COST_BPS/10000.0))/risk if risk else None
    terminal=None
    for h in HORIZONS:
        hend=start+h*3600_000
        if int(now.timestamp()*1000)<hend:continue
        cs=[c for c in candles if int(c["open_time"])<hend]
        if not cs:continue
        hit_stop=hit_tp=False; gross_r=None; event="MARK_TO_MARKET"
        for c in cs:
            hs=c["low"]<=g["stop"] if side=="LONG" else c["high"]>=g["stop"]
            ht=c["high"]>=g["tp2"] if side=="LONG" else c["low"]<=g["tp2"]
            if hs and ht: gross_r=-1.0; event="BOTH_HIT_STOP_FIRST"; hit_stop=True; break
            if hs: gross_r=-1.0; event="STOP"; hit_stop=True; break
            if ht: gross_r=abs(g["tp2"]-g["entry"])/risk; event="TP2"; hit_tp=True; break
        if gross_r is None:
            close=cs[-1]["close"]; gross_r=((close-g["entry"])/risk if side=="LONG" else (g["entry"]-close)/risk)
        net_r=gross_r-(cost_r or 0)
        highs=[c["high"] for c in cs]; lows=[c["low"] for c in cs]
        mfe=((max(highs)-g["entry"])/risk if side=="LONG" else (g["entry"]-min(lows))/risk)
        mae=((g["entry"]-min(lows))/risk if side=="LONG" else (max(highs)-g["entry"])/risk)
        out["horizons"][f"{h}h"]={"gross_r":round(gross_r,4),"net_r_after_cost":round(net_r,4),
          "mfe_r":round(mfe,4),"mae_r":round(mae,4),"event":event,"stop_hit":hit_stop,"tp2_hit":hit_tp}
        terminal=out["horizons"][f"{h}h"]
    out["market_source"]=provider
    out["status"]="MATURED" if "12h" in out["horizons"] else "PARTIAL"
    out["terminal_12h"]=out["horizons"].get("12h")
    return out

def summarize(rows):
    xs=[r for r in rows if r.get("terminal_12h")]
    vals=[r["terminal_12h"]["net_r_after_cost"] for r in xs]
    wins=[x for x in vals if x>0]; losses=[x for x in vals if x<=0]
    gp=sum(wins); gl=abs(sum(losses))
    eq=0.; peak=0.; dd=0.
    for x in vals:
        eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    return {"matured_n":len(vals),"net_r_after_cost":round(sum(vals),4),"avg_net_r_after_cost":round(sum(vals)/len(vals),4) if vals else None,
      "win_rate_pct":round(100*len(wins)/len(vals),2) if vals else None,
      "profit_factor_after_cost":round(gp/gl,4) if gl else ("INF" if gp else None),
      "max_drawdown_r":round(dd,4)}

def settle(history="status/history/regime-transition-frozen-evidence.jsonl"):
    p=Path(history); obs=[]
    if p.exists():
        for line in p.read_text().splitlines():
            try:obs.append(json.loads(line))
            except Exception:pass
    rows=[settle_one(x) for x in obs]
    report={"schema":SCHEMA,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"product_horizon":"4-12H",
      "cost_bps":COST_BPS,"intrabar_both_hit_rule":"STOP_FIRST_CONSERVATIVE","summary":summarize(rows),"records":rows,
      "research_only":True,"live_execution":False,"can_override_production":False,"production_threshold_unchanged":68}
    Path("status/regime-transition-outcomes-latest.json").write_text(json.dumps(report,indent=2,sort_keys=True))
    return report

if __name__=="__main__": print(json.dumps(settle(),sort_keys=True))
