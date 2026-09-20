#!/usr/bin/env python3
"""Build a compact UI-safe Champion vs Reasoning evidence status."""
from __future__ import annotations
import json,pathlib
import market_context_forward_evaluator as evaluator
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/"status/market-context-reasoning-status-latest.json"

def build():
 e=evaluator.build()
 return {"schema":"ATLAS_REASONING_STATUS_V1","title":"Champion vs Reasoning Challenger",
  "stage":"COLLECTING_PROSPECTIVE_EVIDENCE" if not e["promotion_evidence_ready"] else "EVIDENCE_REVIEW_READY",
  "horizons":e["horizons"],"minimum_paired_n_per_horizon":e["minimum_paired_n_per_horizon"],
  "promotion_evidence_ready":e["promotion_evidence_ready"],"production_effect":"NONE",
  "automatic_promotion":False,"research_only":True,"live_execution":False,
  "warning":"Research comparison only. FINAL_TRADE_GATE remains the sole Production decision authority."}
def main():
 x=build();OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(x,indent=2,sort_keys=True));print(json.dumps(x,sort_keys=True))
if __name__=="__main__":main()
