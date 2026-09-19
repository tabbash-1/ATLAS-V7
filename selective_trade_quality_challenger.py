#!/usr/bin/env python3
"""Evidence-only selective trade quality challenger.
Ranks setup families for prospective study; never creates or vetoes Production trades.
"""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
VERSION="ATLAS_SELECTIVE_TRADE_QUALITY_CHALLENGER_V1"
MIN_N=12
def build(root:Path):
 a=json.loads((root/"status/monthly-product-audit-latest.json").read_text())
 cohorts=a.get("qualified_joint_setup_breakdown_nonoverlap_12h") or {}
 rows=[]
 for key,h in cohorts.items():
  s=(h or {}).get("12") or {}; n=int(s.get("n") or 0); mean=s.get("mean_pct"); pos=s.get("positive_rate_pct"); loss=s.get("loss_le_minus_1_pct_rate")
  if n<MIN_N or mean is None: state="INSUFFICIENT_INDEPENDENT_SAMPLE"
  elif float(mean)>0 and float(pos or 0)>=60 and float(loss or 100)<=20: state="QUALITY_CANDIDATE"
  elif float(mean)<0 and float(pos or 0)<=35: state="AVOIDANCE_CANDIDATE"
  else: state="MIXED"
  rows.append({"setup_key":key,"n12_nonoverlap":n,"mean12_pct":mean,"positive12_pct":pos,"loss_ge_1_12_pct":loss,"state":state})
 rows.sort(key=lambda x:(x["state"]!="QUALITY_CANDIDATE",-(x["mean12_pct"] or -999)))
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"source":"status/monthly-product-audit-latest.json","sampling":"NONOVERLAP_12H_SYMBOL_DIRECTION_REGIME_PLAYBOOK","minimum_n":MIN_N,"setups":rows,"safety":{"research_only":True,"paper_only":True,"live_execution":False,"can_override_production":False,"can_create_trade":False,"can_veto_trade":False,"automatic_strategy_change":False},"next_stage":"PROSPECTIVE_CANONICAL_NET_R_VALIDATION","interpretation":"DIRECTIONAL_RETURN_SCREEN_ONLY_NOT_TRADE_EDGE_PROOF"}
def validate(x):
 s=x["safety"];assert s["research_only"] and not s["live_execution"] and not s["can_override_production"] and not s["can_create_trade"] and not s["can_veto_trade"] and not s["automatic_strategy_change"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/selective-trade-quality-latest.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"quality":[z for z in x["setups"] if z["state"]=="QUALITY_CANDIDATE"],"avoid":[z for z in x["setups"] if z["state"]=="AVOIDANCE_CANDIDATE"]},sort_keys=True))
