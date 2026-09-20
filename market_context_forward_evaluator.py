#!/usr/bin/env python3
"""Evaluate prospective reasoning challenger versus canonical champion."""
from __future__ import annotations
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
LEDGER=ROOT/"status/market-context-reasoning-ledger.jsonl"; OUT=ROOT/"status/market-context-reasoning-evaluation-latest.json"
MIN_N=30

def build(path=LEDGER):
 rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
 horizons={}
 for h in ("4","8","12"):
  pairs=[]
  for r in rows:
   o=(r.get("outcomes") or {}).get(h)
   if o is not None:pairs.append((float(o["champion_directional_return"]),float(o["challenger_directional_return"])))
  delta=[b-a for a,b in pairs]
  horizons[h]={"paired_n":len(pairs),"champion_avg":round(sum(a for a,b in pairs)/len(pairs),8) if pairs else None,
    "challenger_avg":round(sum(b for a,b in pairs)/len(pairs),8) if pairs else None,
    "delta_avg":round(sum(delta)/len(delta),8) if delta else None,
    "challenger_better_n":sum(b>a for a,b in pairs),"champion_better_n":sum(a>b for a,b in pairs)}
 ready=all(horizons[h]["paired_n"]>=MIN_N for h in horizons)
 return {"schema":"ATLAS_REASONING_CHALLENGER_EVALUATION_V1","horizons":horizons,
   "promotion_evidence_ready":ready,"promotion_allowed":False,
   "minimum_paired_n_per_horizon":MIN_N,"requires_cost_adjusted_evaluation":True,
   "research_only":True,"production_effect":"NONE","automatic_promotion":False}

def main():
 x=build();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(x,indent=2,sort_keys=True));print(json.dumps(x,sort_keys=True))
if __name__=="__main__":main()
