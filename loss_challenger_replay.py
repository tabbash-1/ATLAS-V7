#!/usr/bin/env python3
"""Evidence-only replay of pre-registered ATLAS loss challengers.
Uses only information available by each checkpoint; never mutates Production.
"""
from __future__ import annotations
import json
from pathlib import Path
import loss_shadow_challengers as contract

VERSION="ATLAS_LOSS_CHALLENGER_REPLAY_V1"
MIN_N=30

def _f(v):
 try:return float(v)
 except Exception:return None

def _cp(row,h):
 for x in row.get("product_window_checkpoints") or []:
  if int(x.get("checkpoint_h") or 0)==h:return x
 return {}

def evaluate_row(row,cost):
 did=str(row.get("decision_id") or row.get("id") or "")
 champion=(cost.get(did) or {}).get("net_r")
 if champion is None:return None
 s=row.get("settlement") or {}; p=row.get("decision_provenance") or {}
 r4=_f(_cp(row,4).get("r_multiple")); r8=_f(_cp(row,8).get("r_multiple"))
 # These are diagnostic replay policies, not promotion evidence. Prospective collection follows separately.
 entry_risk=(p.get("futures_alignment")=="OPPOSED" or
             ((p.get("score_attribution") or {}).get("extension_guard_reason")=="BLOWOFF_RSI_LONG"))
 entry_shadow=0.0 if entry_risk else float(champion)
 early_shadow=float(champion)
 if r4 is not None and r4<=-0.25 and not s.get("tp1_reached"):
  early_shadow=r4
 protect_shadow=float(champion)
 if r8 is not None and r8>=0.15 and not s.get("tp1_reached") and float(champion)<0:
  protect_shadow=max(0.0,r8)
 return {"decision_id":did,"symbol":row.get("symbol"),"direction":row.get("direction"),
         "champion_net_r":round(float(champion),4),
         "ENTRY_CONFIRMATION_DELAY":{"triggered":entry_risk,"shadow_net_r":round(entry_shadow,4),"delta_r":round(entry_shadow-float(champion),4)},
         "EARLY_THESIS_FAILURE":{"triggered":early_shadow!=float(champion),"shadow_net_r":round(early_shadow,4),"delta_r":round(early_shadow-float(champion),4)},
         "PROFIT_PROTECTION_TIME_DECAY":{"triggered":protect_shadow!=float(champion),"shadow_net_r":round(protect_shadow,4),"delta_r":round(protect_shadow-float(champion),4)}}

def build(root=Path(".")):
 v=json.loads((root/"status/production-validation-latest.json").read_text())
 costs={str(x["decision_id"]):x for x in (v.get("post_v2_cost_adjusted") or {}).get("rows") or []}
 rows=[x for x in (evaluate_row(r,costs) for r in v.get("rows") or []) if x]
 names=list(contract.CHALLENGERS)
 reports={}
 for n in names:
  z=[x for x in rows if x[n]["triggered"]]
  reports[n]={"evaluated_n":len(rows),"triggered_n":len(z),
   "observed_delta_r":round(sum(x[n]["delta_r"] for x in rows),4),
   "formal_ready":False,"promotion_allowed":False,
   "interpretation":"RETROSPECTIVE_DIAGNOSTIC_ONLY_NOT_CAUSAL_EVIDENCE"}
 return {"schema":VERSION,"product_horizon":"4-12H","source":"FINAL_TRADE_GATE_POST_V2",
  "contract_schema":contract.VERSION,"rows":rows,"challengers":reports,
  "interpretation":{"retrospective_only":True,"causal_claim_allowed":False,
   "automatic_strategy_change":False,"prospective_paired_min_n":MIN_N},
  "safety":contract.SAFETY}

def validate(x):
 assert x["safety"]["production_impact"]=="NONE"
 assert x["safety"]["production_threshold"]==68
 assert x["interpretation"]["causal_claim_allowed"] is False
 assert all(not z["promotion_allowed"] for z in x["challengers"].values())

if __name__=="__main__":
 x=build(Path(__file__).resolve().parent);validate(x)
 out=Path(__file__).resolve().parent/"status/loss-challenger-replay-latest.json"
 out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"ok":True,"rows":len(x["rows"]),"challengers":x["challengers"]},indent=2))
