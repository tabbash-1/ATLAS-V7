#!/usr/bin/env python3
"""ATLAS evidence-only learning loop coordinator.
Outcome -> diagnosis -> challenger evaluation -> evidence state.
It cannot mutate Production or promote a challenger.
"""
from __future__ import annotations
import datetime as dt,json
from pathlib import Path
import production_failure_attribution as failures
import loss_challenger_replay as replay

VERSION="ATLAS_LEARNING_LOOP_V1"
MIN_N=30

def build(root:Path):
 f=failures.build(root); failures.validate(f)
 r=replay.build(root); replay.validate(r)
 terminal=f["summary"]["terminal"]; losses=f["summary"]["losses"]
 prospective={}
 p=root/"status/opportunity-path-replay-latest.json"
 if p.exists():
  try:
   payload=json.loads(p.read_text(encoding="utf-8"))
   for x in payload.get("hypotheses") or []:
    hid=str(x.get("id") or "")
    if hid:
     prospective[hid]={"paired_n":int(x.get("paired_n") or 0),"evaluable":int(x.get("evaluable") or 0),
      "changed":int(x.get("changed") or 0),"champion_net_r":x.get("champion_net_r"),
      "shadow_net_r":x.get("shadow_net_r"),"delta_net_r":x.get("delta_net_r"),
      "formal_ready":bool(x.get("formal_ready")),"promotion_allowed":False,
      "source":"status/opportunity-path-replay-latest.json"}
  except Exception:
   prospective={}
 candidates={}
 for name,x in r["challengers"].items():
  candidates[name]={"evaluated_n":x["evaluated_n"],"triggered_n":x["triggered_n"],
   "diagnostic_delta_r":x["observed_delta_r"],"state":"COLLECT_FORWARD_EVIDENCE",
   "promotion_allowed":False,"minimum_prospective_paired_n":MIN_N,
   "prospective_evidence":prospective.get(name)}
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
  "pipeline":["OUTCOME","FAILURE_ATTRIBUTION","CHALLENGER_REPLAY","FORWARD_EVIDENCE","HUMAN_REVIEW"],
  "product_horizon":"4-12H","decision_source_of_truth":"FINAL_TRADE_GATE",
  "evidence":{"terminal":terminal,"losses":losses,"attributions":f["summary"]["primary_attributions"],
              "candidates":candidates,"prospective_path_replay":prospective},
  "next_action":"COLLECT_PROSPECTIVE_PAIRED_EVIDENCE",
  "learning_state":"EVIDENCE_COLLECTION",
  "safety":{"research_only":True,"paper_only":True,"live_execution":False,
   "production_impact":"NONE","can_override_production":False,"automatic_promotion":False,
   "automatic_strategy_change":False,"production_threshold":68}}

def validate(x):
 s=x["safety"]
 assert s["production_impact"]=="NONE" and s["production_threshold"]==68
 assert not s["can_override_production"] and not s["automatic_promotion"] and not s["automatic_strategy_change"]
 assert x["pipeline"][-1]=="HUMAN_REVIEW"
 assert all(not z["promotion_allowed"] for z in x["evidence"]["candidates"].values())
 assert all(not z["promotion_allowed"] for z in x["evidence"].get("prospective_path_replay",{}).values())

if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x)
 out=root/"status/learning-loop-latest.json";out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"ok":True,"state":x["learning_state"],"terminal":x["evidence"]["terminal"],"losses":x["evidence"]["losses"],"next":x["next_action"]},indent=2))
