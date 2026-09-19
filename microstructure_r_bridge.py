#!/usr/bin/env python3
"""Evidence-only bridge: decision-time microstructure relation -> canonical R outcomes."""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
VERSION="ATLAS_MICROSTRUCTURE_R_BRIDGE_V1"
def _stats(v):
 return {"n":len(v),"avg_r":round(sum(v)/len(v),4) if v else None,"positive_rate_pct":round(100*sum(x>0 for x in v)/len(v),2) if v else None}
def build(root:Path):
 p=json.loads((root/"status/canonical-outcomes-latest.json").read_text());rows=(p.get("signals") or {}).get("rows") or []
 groups={"ALIGNED":[],"CONTROL":[],"UNKNOWN":[]}
 observations=[]
 for r in rows:
  relation=str(r.get("microstructure_relation_at_entry") or r.get("frozen_entry_context",{}).get("microstructure_relation_at_entry") or "UNKNOWN")
  group="ALIGNED" if relation=="ALIGNED" else "CONTROL" if relation in ("OPPOSED_OR_CROWDED","MIXED_OR_INSUFFICIENT") else "UNKNOWN"
  terminal=r.get("terminal") or {}; rv=terminal.get("r_multiple")
  if rv is None:continue
  rv=float(rv);groups[group].append(rv);observations.append({"decision_id":r.get("decision_id"),"symbol":r.get("symbol"),"direction":r.get("direction"),"relation":relation,"group":group,"terminal_r":rv})
 a=_stats(groups["ALIGNED"]);c=_stats(groups["CONTROL"])
 delta=round(a["avg_r"]-c["avg_r"],4) if a["avg_r"] is not None and c["avg_r"] is not None else None
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"research_only":True,"live_execution":False,"can_override_production":False,"automatic_strategy_change":False,"interpretation":"DESCRIPTIVE_CANONICAL_R_BRIDGE_NOT_FORWARD_EDGE_PROOF","groups":{"aligned":a,"control":c,"unknown":_stats(groups["UNKNOWN"])},"aligned_minus_control_avg_r":delta,"observations":observations}
def validate(x):
 assert x["research_only"] and not x["live_execution"] and not x["can_override_production"] and not x["automatic_strategy_change"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/microstructure-r-bridge-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"groups":x["groups"],"delta":x["aligned_minus_control_avg_r"]},sort_keys=True))
