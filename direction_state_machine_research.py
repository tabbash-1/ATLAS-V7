"""ATLAS Direction State Machine V1 — research/shadow only.

Combines independently researched transition states without granting execution
authority. Critical invariant: LONG cannot flip directly to SHORT. Exhaustion and
reversal caution first de-risk confidence; SHORT requires a later independent
confirmation that is intentionally unimplemented until evidence exists.
"""
from __future__ import annotations
VERSION="ATLAS_DIRECTION_STATE_MACHINE_V1"
STATES=("NEUTRAL","EARLY_LONG","CONFIRMED_LONG","EXPANSION_LONG","LONG_EXHAUSTION_CAUTION","REVERSAL_CAUTION","SHORT_UNVALIDATED")

def transition(previous, *, early_long=False, long_confirmed=False, expansion=False,
               exhaustion=False, reversal_caution=False, short_confirmed=False):
    p=str(previous or "NEUTRAL").upper()
    state=p if p in STATES else "NEUTRAL"
    reason="HOLD_STATE"
    if exhaustion and state in {"EARLY_LONG","CONFIRMED_LONG","EXPANSION_LONG"}:
        state="LONG_EXHAUSTION_CAUTION";reason="BTC_OVEREXTENSION_WITH_BROAD_BULLISH_PARTICIPATION"
    elif reversal_caution and state=="LONG_EXHAUSTION_CAUTION":
        state="REVERSAL_CAUTION";reason="BULLISH_BREADTH_COLLAPSE_WITH_FALLING_BTC_RSI"
    elif short_confirmed and state=="REVERSAL_CAUTION":
        # Evidence is not sufficient to authorize an actionable SHORT in V1.
        state="SHORT_UNVALIDATED";reason="SHORT_CONFIRMATION_REQUIRES_PROSPECTIVE_VALIDATION"
    elif early_long and state=="NEUTRAL":
        state="EARLY_LONG";reason="EARLY_LONG_TRANSITION"
    elif long_confirmed and state=="EARLY_LONG":
        state="CONFIRMED_LONG";reason="LONG_CONFIRMED"
    elif expansion and state=="CONFIRMED_LONG":
        state="EXPANSION_LONG";reason="LONG_EXPANSION"
    return {
      "version":VERSION,"previous_state":p,"state":state,"reason":reason,
      "actionable_direction":"LONG" if state in {"CONFIRMED_LONG","EXPANSION_LONG"} else "WAIT",
      "research_only":True,"shadow_only":True,"paper_only":True,
      "direct_long_to_short_allowed":False,"short_execution_validated":False,
      "can_override_production":False,"can_override_final_gate":False,
      "can_force_exit":False,"live_execution":False,
    }
