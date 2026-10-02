"""ATLAS market breadth exhaustion challenger — research/shadow only.

Hypothesis discovered on historical replay: a broad LONG state may be late/exhausted
when breadth remains strongly bullish while BTC itself is already overextended.
This module NEVER emits SHORT, never changes Production, and is not a validated exit.
It only marks LONG_EXHAUSTION_CAUTION for prospective validation.
"""
from __future__ import annotations
VERSION="ATLAS_MARKET_BREADTH_EXHAUSTION_V1"
def _f(v):
    try:return float(v)
    except (TypeError,ValueError):return None
def assess(*,bullish_ratio,btc_trend,btc_rsi14,btc_momentum_24h_pct):
    br=_f(bullish_ratio); rsi=_f(btc_rsi14); mom=_f(btc_momentum_24h_pct)
    missing=[k for k,v in (("BREADTH",br),("BTC_RSI",rsi),("BTC_MOMENTUM",mom)) if v is None]
    caution=bool(not missing and str(btc_trend or "").upper()=="BULLISH" and br>=0.60 and rsi>=77.0 and mom>=2.0)
    return {
      "version":VERSION,
      "state":"LONG_EXHAUSTION_CAUTION" if caution else "NO_EXHAUSTION_EVIDENCE",
      "eligible":caution,
      "missing":missing,
      "research_only":True,"shadow_only":True,"paper_only":True,
      "can_emit_short":False,"can_force_exit":False,
      "can_override_production":False,"can_override_final_gate":False,
      "can_change_threshold":False,"live_execution":False,
      "hypothesis_thresholds":{"bullish_ratio_min":0.60,"btc_rsi14_min":77.0,"btc_momentum_24h_pct_min":2.0},
    }
