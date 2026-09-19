#!/usr/bin/env python3
"""Research-only calibration of frozen Production score against cost-adjusted terminal R."""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
VERSION="ATLAS_COST_ADJUSTED_SCORE_CALIBRATION_V1"
def band(s):
 s=float(s);return "82_PLUS" if s>=82 else "75_81" if s>=75 else "68_74" if s>=68 else "BELOW_68"
def stats(v):
 return {"n":len(v),"avg_net_r":round(sum(v)/len(v),4) if v else None,"net_r":round(sum(v),4),"positive_rate_pct":round(100*sum(x>0 for x in v)/len(v),2) if v else None}
def build(root:Path):
 p=json.loads((root/"status/production-validation-latest.json").read_text());scores={str(x.get("decision_id") or x.get("id")):x.get("score") for x in p.get("rows") or []}
 groups={};rows=[]
 for x in (p.get("post_v2_cost_adjusted") or {}).get("rows") or []:
  did=str(x.get("decision_id"));s=scores.get(did)
  if s is None:continue
  b=band(s);nr=float(x["net_r"]);groups.setdefault(b,[]).append(nr);rows.append({"decision_id":did,"symbol":x.get("symbol"),"direction":x.get("direction"),"score":s,"band":b,"net_r":nr,"estimated_cost_r":x.get("estimated_cost_r")})
 out={k:stats(v) for k,v in groups.items()}
 high=out.get("82_PLUS");lower=[r["net_r"] for r in rows if r["band"] in ("68_74","75_81")]
 warning=None
 if high and high["n"]>=5 and len(lower)>=5 and high["avg_net_r"]<=sum(lower)/len(lower):warning="HIGH_SCORE_NOT_OUTPERFORMING_LOWER_QUALIFIED_AFTER_COSTS"
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"research_only":True,"paper_only":True,"live_execution":False,"can_override_production":False,"automatic_strategy_change":False,"production_threshold_changed":False,"production_threshold":68,"source":"status/production-validation-latest.json/post_v2_cost_adjusted","bands":out,"warning":warning,"rows":rows,"interpretation":"DESCRIPTIVE_SMALL_SAMPLE_COST_ADJUSTED_CALIBRATION_NOT_PROMOTION_EVIDENCE"}
def validate(x):
 assert x["research_only"] and x["paper_only"] and not x["live_execution"] and not x["can_override_production"] and not x["automatic_strategy_change"] and not x["production_threshold_changed"] and x["production_threshold"]==68
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/cost-adjusted-score-calibration-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"bands":x["bands"],"warning":x["warning"]},sort_keys=True))
