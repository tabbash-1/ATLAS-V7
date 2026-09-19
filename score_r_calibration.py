#!/usr/bin/env python3
"""Evidence-only calibration of frozen Production score against canonical 4/8/12H R outcomes."""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
VERSION="ATLAS_SCORE_R_CALIBRATION_V1";HORIZONS=(4,8,12)
BANDS=((0,67,"BELOW_68"),(68,74,"68_74"),(75,81,"75_81"),(82,100,"82_PLUS"))
def _band(score):
 for lo,hi,name in BANDS:
  if lo<=score<=hi:return name
 return "OTHER"
def _stats(vals):
 if not vals:return {"n":0,"avg_r":None,"positive_rate_pct":None}
 return {"n":len(vals),"avg_r":round(sum(vals)/len(vals),4),"positive_rate_pct":round(100*sum(v>0 for v in vals)/len(vals),2)}
def build(root:Path):
 payload=json.loads((root/"status/canonical-outcomes-latest.json").read_text());rows=(payload.get("signals") or {}).get("rows") or []
 by_h={};pairs=[]
 for h in HORIZONS:
  groups={}
  for r in rows:
   score=r.get("score")
   if score is None:continue
   cp=next((x for x in (r.get("product_window_checkpoints") or []) if int(x.get("checkpoint_h") or -1)==h and x.get("matured")),None)
   if not cp or cp.get("r_multiple") is None:continue
   groups.setdefault(_band(float(score)),[]).append(float(cp["r_multiple"]))
   pairs.append({"decision_id":r.get("decision_id"),"symbol":r.get("symbol"),"direction":r.get("direction"),"score":score,"score_band":_band(float(score)),"horizon_h":h,"r_multiple":cp["r_multiple"]})
  by_h[str(h)]={k:_stats(v) for k,v in groups.items()}
 high12=[x["r_multiple"] for x in pairs if x["horizon_h"]==12 and x["score"]>=82];low12=[x["r_multiple"] for x in pairs if x["horizon_h"]==12 and 68<=x["score"]<82]
 warning="HIGH_SCORE_NOT_OUTPERFORMING_LOWER_QUALIFIED_SCORE" if len(high12)>=5 and len(low12)>=5 and sum(high12)/len(high12)<=sum(low12)/len(low12) else None
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"decision_source_of_truth":"FINAL_TRADE_GATE","product_horizon":"4-12H","methodology":"Frozen canonical paper entries only; score evaluated against observed R at 4H/8H/12H. No Production mutation.","by_horizon_score_band":by_h,"observations":pairs,"calibration_warning":warning,"safety":{"research_only":True,"paper_only":True,"live_execution":False,"can_override_production":False,"automatic_strategy_change":False,"threshold_changed":False,"production_threshold":68}}
def validate(x):
 s=x["safety"];assert s["research_only"] and s["paper_only"] and not s["live_execution"] and not s["can_override_production"] and not s["automatic_strategy_change"] and not s["threshold_changed"] and s["production_threshold"]==68
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);out=root/"status/score-r-calibration-latest.json";out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"warning":x["calibration_warning"],"bands":x["by_horizon_score_band"]},sort_keys=True))
