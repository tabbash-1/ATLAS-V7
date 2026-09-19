#!/usr/bin/env python3
"""Evidence-only profile of what actual canonical winners look like.
Uses only frozen/settled trade facts and cost-adjusted net R. No Production effect.
"""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
VERSION="ATLAS_WINNING_TRADE_PROFILE_V1"
def _f(x):
 try:return float(x)
 except:return None
def build(root:Path):
 p=json.loads((root/"status/production-validation-latest.json").read_text())
 costs={r["decision_id"]:r for r in (p.get("post_v2_cost_adjusted") or {}).get("rows") or []}
 rows=[]
 for r in p.get("rows") or []:
  did=r.get("decision_id") or r.get("id"); c=costs.get(did)
  if not c: continue
  s=r.get("settlement") or {}; net=_f(c.get("net_r")); mfe=_f(s.get("mfe_r")); mae=_f(s.get("mae_r"))
  rows.append({"decision_id":did,"symbol":r.get("symbol"),"direction":r.get("direction"),"score":_f(r.get("score")),"net_r":net,"winner_after_costs":bool(net is not None and net>0),"mfe_r":mfe,"mae_r":mae,"tp1_reached":bool(s.get("tp1_reached")),"holding_hours":_f(c.get("holding_hours")),"estimated_cost_r":_f(c.get("estimated_cost_r")),"rr_tp2":_f((r.get("geometry") or {}).get("rr_tp2"))})
 wins=[x for x in rows if x["winner_after_costs"]]; losses=[x for x in rows if not x["winner_after_costs"]]
 def profile(z):
  def avg(k):
   a=[x[k] for x in z if x.get(k) is not None];return round(sum(a)/len(a),4) if a else None
  return {"n":len(z),"avg_net_r":avg("net_r"),"avg_score":avg("score"),"avg_mfe_r":avg("mfe_r"),"avg_mae_r":avg("mae_r"),"avg_holding_hours":avg("holding_hours"),"avg_cost_r":avg("estimated_cost_r"),"tp1_rate_pct":round(100*sum(x["tp1_reached"] for x in z)/len(z),2) if z else None,"long_n":sum(x["direction"]=="LONG" for x in z),"short_n":sum(x["direction"]=="SHORT" for x in z)}
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"epoch":(p.get("epoch") or {}).get("id"),"objective":"IDENTIFY_PRE_ENTRY_CHARACTERISTICS_OF_COST_ADJUSTED_WINNERS","winner_definition":"net_r > 0 after modeled fees/slippage/funding","profiles":{"winners":profile(wins),"non_winners":profile(losses)},"rows":rows,"limitations":["SMALL_SAMPLE","POST_ENTRY_MFE_MAE_HOLDING_ARE_DIAGNOSTIC_ONLY_NOT_ENTRY_FEATURES","NO_RETROACTIVE_FEATURE_INFERENCE"],"next_stage":"JOIN_ONLY_FROZEN_DECISION_TIME_FEATURES_THEN_PROSPECTIVE_VALIDATE","safety":{"research_only":True,"paper_only":True,"can_override_production":False,"can_create_trade":False,"can_veto_trade":False,"automatic_strategy_change":False}}
def validate(x):
 s=x["safety"];assert s["research_only"] and not s["can_override_production"] and not s["can_create_trade"] and not s["can_veto_trade"] and not s["automatic_strategy_change"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/winning-trade-profile-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"profiles":x["profiles"]},sort_keys=True))
