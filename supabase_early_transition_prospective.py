"""Prospective capture contract for Supabase Early Transition V1.

This adapter intentionally accepts only same-T0 evidence supplied by the caller.
It does not nearest-time join legacy Supabase rows to Production snapshots because
the two historical clocks were not synchronized closely enough for causal replay.
"""
from __future__ import annotations
from supabase_early_transition_research import assess

VERSION="ATLAS_SUPABASE_EARLY_TRANSITION_PROSPECTIVE_V1"

def capture(production_observation, same_t0_features):
    p=production_observation or {}; f=same_t0_features or {}
    candidate=assess(f)
    return {
      "version":VERSION,
      "captured_at":p.get("captured_at"),
      "symbol":p.get("symbol"),
      "canonical_decision_id":p.get("canonical_decision_id"),
      "canonical_decision":p.get("canonical_decision"),
      "early_transition":candidate,
      "provenance_policy":"SAME_T0_ONLY_NO_NEAREST_TIME_LEGACY_JOIN",
      "historical_cross_system_replay_valid":False,
      "research_only":True,"paper_only":True,
      "can_override_production":False,"can_override_final_gate":False,
      "can_change_threshold":False,"live_execution":False,
    }

def promotion_eligible(_records):
    # Promotion is deliberately impossible in V1. Prospective evidence must first
    # be accumulated and evaluated by the existing governance/promotion process.
    return False
