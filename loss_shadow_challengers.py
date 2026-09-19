#!/usr/bin/env python3
"""Research-only loss challenger definitions for ATLAS 4-12H.
No Production decision, threshold, geometry, SL/TP or execution mutation.
These candidates must be evaluated prospectively before any promotion.
"""
from __future__ import annotations

VERSION="ATLAS_LOSS_SHADOW_CHALLENGERS_V1"
PRODUCTION_THRESHOLD=68

CHALLENGERS={
 "ENTRY_CONFIRMATION_DELAY":{
   "purpose":"Test delayed confirmation when entry-time evidence is conflicted or extension risk is elevated.",
   "trigger_inputs":["futures_alignment","extension_guard_reason","momentum_adjustment"],
   "action":"SHADOW_DELAY_ONLY",
   "evaluation":"paired net R vs canonical entry at 4h/8h/12h",
 },
 "EARLY_THESIS_FAILURE":{
   "purpose":"Test whether absent follow-through after entry predicts later full-risk invalidation.",
   "trigger_inputs":["post_entry_mfe_r","elapsed_h"],
   "action":"SHADOW_EARLY_EXIT_ONLY",
   "evaluation":"paired net R vs canonical settlement",
 },
 "PROFIT_PROTECTION_TIME_DECAY":{
   "purpose":"Test protection after meaningful favorable excursion that fails to convert before horizon decay.",
   "trigger_inputs":["post_entry_mfe_r","tp1_reached","elapsed_h"],
   "action":"SHADOW_PROTECTION_ONLY",
   "evaluation":"paired net R vs canonical settlement",
 },
}

SAFETY={
 "research_only":True,"paper_only":True,"live_execution":False,
 "can_override_production":False,"production_impact":"NONE",
 "changes_threshold":False,"production_threshold":68,
 "changes_score":False,"changes_geometry":False,"changes_sl_tp":False,
 "changes_final_trade_gate":False,"hindsight_promotion_allowed":False,
}

def contract():
 return {"schema":VERSION,"product_horizon":"4-12H","challengers":CHALLENGERS,"safety":SAFETY,
 "promotion":{"automatic":False,"requires_prospective_paired_evidence":True,
 "minimum_paired_sample":30,"metric":"cost_adjusted_net_r","split_by_direction":True}}

def validate():
 p=contract(); s=p["safety"]
 assert s["research_only"] and not s["live_execution"] and not s["can_override_production"]
 assert s["production_threshold"]==PRODUCTION_THRESHOLD
 assert not any(s[k] for k in ("changes_threshold","changes_score","changes_geometry","changes_sl_tp","changes_final_trade_gate"))
 assert p["promotion"]["minimum_paired_sample"]>=30
 return p

if __name__=="__main__":
 import json; print(json.dumps(validate(),indent=2,sort_keys=True))
