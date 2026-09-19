#!/usr/bin/env python3
"""Pre-registered winning-setup fingerprint challenger.
Learns no weights and never changes Production. It defines a small, interpretable
entry-time fingerprint from frozen fields, then waits for prospective net-R evidence.
"""
from __future__ import annotations
import json,datetime as dt,hashlib
from pathlib import Path
VERSION="ATLAS_WINNING_SETUP_FINGERPRINT_V1"
RULE={"htf_v2_eligible":True,"breakout_confirmed":True,"allowed_playbooks":["BREAKOUT_CONFIRMED_LONG","BREAKOUT_CONTINUATION_LONG"],"disallowed_htf_alignment":["NO_ENTRY_CONFIRMATION_DIRECTION"],"require_futures_not_opposed":False}
MIN_MATCHED=15;MIN_CONTROL=15
def match(p):
 if p.get("frozen_before_outcome") is not True:return False
 if p.get("htf_v2_eligible") is not RULE["htf_v2_eligible"]:return False
 if p.get("breakout_confirmed") is not RULE["breakout_confirmed"]:return False
 if p.get("playbook") not in RULE["allowed_playbooks"]:return False
 if p.get("htf_alignment_class") in RULE["disallowed_htf_alignment"]:return False
 if RULE["require_futures_not_opposed"] and p.get("futures_alignment")=="OPPOSED":return False
 return True
def build(root:Path):
 src=json.loads((root/"status/production-validation-latest.json").read_text());cost={x["decision_id"]:x for x in (src.get("post_v2_cost_adjusted") or {}).get("rows") or []};rows=[]
 for r in src.get("rows") or []:
  p=r.get("decision_provenance")
  if not isinstance(p,dict) or p.get("frozen_before_outcome") is not True:continue
  c=cost.get(r.get("decision_id")); 
  if not c:continue
  rows.append({"decision_id":r.get("decision_id"),"matched":match(p),"net_r":c.get("net_r"),"symbol":r.get("symbol"),"direction":r.get("direction")})
 def s(z):
  rs=[float(x["net_r"]) for x in z if x.get("net_r") is not None];return {"n":len(rs),"net_r":round(sum(rs),4),"avg_net_r":round(sum(rs)/len(rs),4) if rs else None,"positive_rate_pct":round(100*sum(v>0 for v in rs)/len(rs),2) if rs else None}
 a=[x for x in rows if x["matched"]];b=[x for x in rows if not x["matched"]];sa,sb=s(a),s(b)
 ready=sa["n"]>=MIN_MATCHED and sb["n"]>=MIN_CONTROL
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"rule":RULE,"rule_hash":hashlib.sha256(json.dumps(RULE,sort_keys=True).encode()).hexdigest(),"preregistration":{"minimum_matched":MIN_MATCHED,"minimum_control":MIN_CONTROL,"rule_mutation_after_outcome_allowed":False},"current_descriptive_only":{"matched":sa,"control":sb,"rows":rows},"state":"FORMAL_REVIEW_READY" if ready else "COLLECTING_PROSPECTIVE_SAMPLE","promotion_allowed":False,"interpretation":"CURRENT_ROWS_ARE_NOT_PROSPECTIVE_PROOF_RULE_IS_FROZEN_FOR_FUTURE_EVALUATION","safety":{"research_only":True,"paper_only":True,"can_override_production":False,"can_create_trade":False,"can_veto_trade":False,"automatic_strategy_change":False}}
def validate(x):
 assert x["promotion_allowed"] is False and x["preregistration"]["rule_mutation_after_outcome_allowed"] is False and not x["safety"]["can_override_production"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/winning-setup-fingerprint-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"state":x["state"],"current":x["current_descriptive_only"]},sort_keys=True))
