#!/usr/bin/env python3
"""Evaluate frozen prospective fingerprint groups against cost-adjusted net R."""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
VERSION="ATLAS_FINGERPRINT_PROSPECTIVE_EVALUATOR_V1"
MIN_N=15
def _read(p,d):
 try:return json.loads(p.read_text())
 except:return d
def _stats(rows):
 rs=[float(x["net_r"]) for x in rows if x.get("net_r") is not None]
 pos=[x for x in rs if x>0];neg=[x for x in rs if x<0]
 gp=sum(pos);gl=abs(sum(neg))
 return {"n":len(rs),"net_r":round(sum(rs),4),"avg_net_r":round(sum(rs)/len(rs),4) if rs else None,"win_rate_pct":round(100*len(pos)/len(rs),2) if rs else None,"profit_factor":round(gp/gl,4) if gl else (None if not gp else "INF")}
def build(root:Path):
 ledger=_read(root/"status/fingerprint-prospective-ledger.json",{"entries":[]});pv=_read(root/"status/production-validation-latest.json",{})
 costs={x["decision_id"]:x for x in (pv.get("post_v2_cost_adjusted") or {}).get("rows") or []}
 settled=[]
 for e in ledger.get("entries") or []:
  if e.get("evidence_class") != "FORMAL_PROSPECTIVE":continue
  c=costs.get(e.get("decision_id"))
  if c and c.get("net_r") is not None:settled.append({"decision_id":e["decision_id"],"group":e["fingerprint_group"],"net_r":c["net_r"],"symbol":e.get("symbol"),"direction":e.get("direction")})
 m=_stats([x for x in settled if x["group"]=="MATCHED"]);c=_stats([x for x in settled if x["group"]=="CONTROL"])
 ready=m["n"]>=MIN_N and c["n"]>=MIN_N
 delta=None if not ready else round(m["avg_net_r"]-c["avg_net_r"],4)
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"settled_rows":settled,"groups":{"matched":m,"control":c},"formal_sample_ready":ready,"matched_minus_control_avg_net_r":delta,"edge_claim_allowed":False,"state":"FORMAL_REVIEW_READY" if ready else "COLLECTING_PROSPECTIVE_COST_ADJUSTED_OUTCOMES","interpretation":"FORMAL_EVALUATION_USES_ONLY_FIRST_SEEN_UNRESOLVED_ASSIGNMENTS","safety":{"research_only":True,"paper_only":True,"can_override_production":False,"can_create_trade":False,"can_veto_trade":False,"automatic_strategy_change":False}}
def validate(x):
 assert x["edge_claim_allowed"] is False and not x["safety"]["can_override_production"] and not x["safety"]["automatic_strategy_change"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/fingerprint-prospective-evaluation-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"state":x["state"],"groups":x["groups"]},sort_keys=True))
