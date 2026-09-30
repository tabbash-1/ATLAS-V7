#!/usr/bin/env python3
"""ADP V1: evaluate frozen direction-alignment hypotheses without Production mutation."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def load(p):
    with open(ROOT/p,encoding="utf-8") as f:return json.load(f)

def wilson(k,n,z=1.96):
    if not n:return None
    p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=z*((p*(1-p)/n+z*z/(4*n*n))**.5)/d
    return [round(100*(c-h),2),round(100*(c+h),2)]

def main():
    g=load("status/prospective-direction-guardrail-latest.json")
    groups={}
    for name,x in g.get("groups",{}).items():
        n=int(x.get("n") or 0); rate=float(x.get("positive_rate_pct") or 0)
        k=round(n*rate/100)
        groups[name]={
          "n":n,"direction_accuracy_pct":rate,"mean_directional_return_pct":x.get("mean_pct"),
          "wilson_95_pct":wilson(k,n),
          "claim_ready":bool(g.get("claims",{}).get("claims_ready")),
        }
    out={
      "schema":"ADP_DIRECTION_BASELINE_V1",
      "research_only":True,"production_effect":"NONE",
      "source_schema":g.get("schema"),"source_generated_at":g.get("generated_at"),
      "target_horizon_h":g.get("target_horizon_hours"),"groups":groups,
      "interpretation":"Regime-aligned direction is a candidate feature, not a proven trading edge. Confidence intervals and prospective replication are required."
    }
    p=ROOT/"research/adp/direction_baseline_v1.json";p.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
