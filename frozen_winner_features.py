#!/usr/bin/env python3
"""Compare winners vs losses using ONLY frozen decision-time provenance."""
from __future__ import annotations
import json,datetime as dt
from collections import defaultdict
from pathlib import Path
VERSION="ATLAS_FROZEN_WINNER_FEATURES_V1"
def _f(x):
 try:return float(x)
 except:return None
def build(root:Path):
 p=json.loads((root/"status/production-validation-latest.json").read_text())
 costs={r["decision_id"]:r for r in (p.get("post_v2_cost_adjusted") or {}).get("rows") or []}
 rows=[]
 for r in p.get("rows") or []:
  prov=r.get("decision_provenance")
  if not isinstance(prov,dict) or prov.get("frozen_before_outcome") is not True:continue
  c=costs.get(r.get("decision_id") or r.get("id"))
  if not c:continue
  a=prov.get("score_attribution") or {};net=_f(c.get("net_r"))
  rows.append({"decision_id":r.get("decision_id"),"symbol":r.get("symbol"),"direction":r.get("direction"),"net_r":net,"winner":net is not None and net>0,"score":_f(prov.get("score")),"market_regime":prov.get("market_regime"),"playbook":prov.get("playbook"),"htf_v2_eligible":prov.get("htf_v2_eligible"),"htf_alignment_class":prov.get("htf_alignment_class"),"futures_alignment":prov.get("futures_alignment"),"breakout_confirmed":prov.get("breakout_confirmed"),"continuation_strong":prov.get("continuation_strong"),"relative_volume":_f(prov.get("relative_volume")),"extension_guard_reason":a.get("extension_guard_reason"),"relative_strength_reason":a.get("relative_strength_reason"),"momentum_adjustment":_f(a.get("momentum_adjustment"))})
 def categorical(field):
  d=defaultdict(lambda:{"n":0,"wins":0,"net_r":0.0})
  for x in rows:
   k=str(x.get(field));z=d[k];z["n"]+=1;z["wins"]+=int(x["winner"]);z["net_r"]+=x["net_r"] or 0
  return {k:{"n":v["n"],"win_rate_pct":round(100*v["wins"]/v["n"],2),"net_r":round(v["net_r"],4),"avg_net_r":round(v["net_r"]/v["n"],4)} for k,v in sorted(d.items())}
 fields=["direction","market_regime","playbook","htf_v2_eligible","htf_alignment_class","futures_alignment","breakout_confirmed","continuation_strong","extension_guard_reason","relative_strength_reason"]
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"eligible_rows":len(rows),"rows":rows,"feature_summaries":{f:categorical(f) for f in fields},"interpretation":{"causal_claim_allowed":False,"promotion_allowed":False,"reason":"SMALL_FROZEN_PROVENANCE_SAMPLE_REQUIRES_PROSPECTIVE_VALIDATION"},"safety":{"research_only":True,"paper_only":True,"uses_only_frozen_entry_features":True,"can_override_production":False,"automatic_strategy_change":False}}
def validate(x):
 assert x["safety"]["uses_only_frozen_entry_features"] and not x["safety"]["can_override_production"] and not x["safety"]["automatic_strategy_change"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/frozen-winner-features-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"eligible":x["eligible_rows"],"summaries":x["feature_summaries"]},sort_keys=True))
