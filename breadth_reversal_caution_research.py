"""ATLAS breadth reversal caution — research/shadow only.

Historical hypothesis: after broad bullish participation, a rapid loss of bullish
breadth together with falling BTC RSI may mark transition from exhaustion toward
reversal. One historical occurrence is insufficient to authorize SHORT.
"""
from __future__ import annotations
VERSION="ATLAS_BREADTH_REVERSAL_CAUTION_V1"
def _f(v):
    try:return float(v)
    except (TypeError,ValueError):return None
def assess(*,previous_bullish_ratio,bullish_ratio,lost_bullish_ratio,btc_rsi_delta):
    p=_f(previous_bullish_ratio);b=_f(bullish_ratio);lost=_f(lost_bullish_ratio);dr=_f(btc_rsi_delta)
    missing=[k for k,v in (("PREVIOUS_BREADTH",p),("BREADTH",b),("LOST_BREADTH",lost),("BTC_RSI_DELTA",dr)) if v is None]
    caution=bool(not missing and p>=.60 and b<p and lost>=.20 and dr<0)
    return {
      "version":VERSION,"state":"REVERSAL_CAUTION" if caution else "NO_REVERSAL_EVIDENCE",
      "eligible":caution,"missing":missing,
      "research_only":True,"shadow_only":True,"paper_only":True,
      "can_emit_short":False,"can_force_exit":False,"can_override_production":False,
      "can_override_final_gate":False,"can_change_threshold":False,"live_execution":False,
    }
