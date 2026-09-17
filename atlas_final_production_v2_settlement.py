#!/usr/bin/env python3
"""ATLAS Phase 6 final Production V2 settlement.
This is an evidence-controlled release decision record, not a trading engine wrapper.
If Phase 5 has no passing cohort, current Production is preserved exactly.
"""
from __future__ import annotations
import json, pathlib, datetime
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'status/promotion-gate-latest.json'
OUT=ROOT/'status/final-production-v2-latest.json'
SCHEMA='ATLAS_FINAL_PRODUCTION_V2_SETTLEMENT_V1'
CURRENT_THRESHOLD=68

def settle(d):
    decision=d.get('promotion_decision'); passing=d.get('passing_cohorts') or []
    eligible=decision=='ELIGIBLE_FOR_MANUAL_PRODUCTION_REVIEW' and bool(passing)
    # Phase 6 never silently promotes. Evidence eligibility requires a separate explicit implementation PR.
    action='PRESERVE_CURRENT_PRODUCTION' if not eligible else 'MANUAL_IMPLEMENTATION_REVIEW_REQUIRED'
    return {'schema':SCHEMA,'phase':'6_OF_6','generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_schema':d.get('schema'),'source_promotion_decision':decision,'passing_cohorts':passing,'final_release_action':action,'production_changed':False,'production_impact':'NONE','automatic_promotion':False,'research_only':False,'live_execution_change':False,'threshold_before':CURRENT_THRESHOLD,'threshold_after':CURRENT_THRESHOLD,'score_logic_changed':False,'risk_logic_changed':False,'sl_tp_logic_changed':False,'final_trade_gate_changed':False,'new_performance_epoch_required':False if action=='PRESERVE_CURRENT_PRODUCTION' else True,'evidence_policy':'NO_PROMOTION preserves the current canonical Production. Any future evidence-backed semantic promotion requires an explicit implementation PR, regression suite, deployment verification, and a new performance epoch.'}

def main():
    d=json.loads(SOURCE.read_text()); report=settle(d)
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
