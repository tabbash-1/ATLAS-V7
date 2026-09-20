#!/usr/bin/env python3
"""Evaluate immutable prospective reasoning challenger versus canonical champion."""
from __future__ import annotations
import json,pathlib
import market_context_forward_ledger as ledger
ROOT=pathlib.Path(__file__).resolve().parent
LEDGER=ledger.OUT; SETTLEMENTS=ledger.SETTLEMENT_OUT; OUT=ROOT/"status/market-context-reasoning-evaluation-latest.json"; MIN_N=30
def _read(path):
 return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
def build(path=LEDGER,settlements_path=SETTLEMENTS):
 captures={x.get("observation_id"):x for x in _read(path) if x.get("observation_id")}
 settled=_read(settlements_path); horizons={}
 for h in (4,8,12):
  pairs=[]
  for s in settled:
   if int(s.get("horizon_h",-1))!=h or s.get("observation_id") not in captures:continue
   pairs.append((float(s["champion_directional_return"]),float(s["challenger_directional_return"])))
  delta=[b-a for a,b in pairs]
  horizons[str(h)]={"paired_n":len(pairs),"champion_avg":round(sum(a for a,b in pairs)/len(pairs),8) if pairs else None,
   "challenger_avg":round(sum(b for a,b in pairs)/len(pairs),8) if pairs else None,
   "delta_avg":round(sum(delta)/len(delta),8) if delta else None,"challenger_better_n":sum(b>a for a,b in pairs),"champion_better_n":sum(a>b for a,b in pairs)}
 ready=all(horizons[str(h)]["paired_n"]>=MIN_N for h in (4,8,12))
 return {"schema":"ATLAS_REASONING_CHALLENGER_EVALUATION_V2_IMMUTABLE","horizons":horizons,"promotion_evidence_ready":ready,
 "promotion_allowed":False,"minimum_paired_n_per_horizon":MIN_N,"requires_cost_adjusted_evaluation":True,"research_only":True,"production_effect":"NONE","automatic_promotion":False}
def main():
 x=build();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(x,indent=2,sort_keys=True));print(json.dumps(x,sort_keys=True))
if __name__=="__main__":main()
