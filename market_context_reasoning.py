"""ATLAS Market Context Reasoning Challenger V1.

Shadow-only context synthesis inspired by independent analyst reasoning.
It never changes FINAL_TRADE_GATE, Production score, threshold or geometry.
The output is designed for prospective 4/8/12H comparison against canonical ATLAS.
"""
from __future__ import annotations

VERSION="ATLAS_MARKET_CONTEXT_REASONING_V1_SHADOW"

def _n(v):
    try: return float(v)
    except Exception: return None

def _u(v): return str(v or "").strip().upper()

def build(context):
    c=context or {}
    direction=_u(c.get("trend_direction"))
    ret7=_n(c.get("return_7d_pct")); ret30=_n(c.get("return_30d_pct"))
    rsi=_n(c.get("rsi")); dist=_n(c.get("distance_from_recent_high_pct"))
    news=_u(c.get("event_risk")); catalyst=_u(c.get("catalyst_bias"))
    htf=_u(c.get("htf_alignment"))
    liquidity=_u(c.get("liquidity_bias")); whale=_u(c.get("whale10_consensus"))
    extra_e=list(c.get("enrichment_evidence") or []); extra_p=list(c.get("enrichment_pressures") or [])
    evidence=list(extra_e); pressures=list(extra_p)

    bullish=direction=="LONG"
    bearish=direction=="SHORT"
    if bullish: evidence.append("PRIMARY_TREND_UP")
    if bearish: evidence.append("PRIMARY_TREND_DOWN")
    if catalyst=="POSITIVE": evidence.append("POSITIVE_CATALYST_CONTEXT")
    if catalyst=="NEGATIVE": pressures.append("NEGATIVE_CATALYST_CONTEXT")
    if news in ("HIGH","CRITICAL"): pressures.append("EVENT_RISK_"+news)

    overextended=False
    if bullish and ((ret7 is not None and ret7>=20) or (ret30 is not None and ret30>=60) or (rsi is not None and rsi>=72)):
        overextended=True; pressures.append("BULLISH_OVEREXTENSION")
    if bearish and ((ret7 is not None and ret7<=-20) or (ret30 is not None and ret30<=-60) or (rsi is not None and rsi<=28)):
        overextended=True; pressures.append("BEARISH_OVEREXTENSION")
    if dist is not None and abs(dist)<=3: evidence.append("NEAR_RECENT_EXTREME")

    opposition=(bullish and (liquidity=="ASK" or whale=="DISTRIBUTION")) or (bearish and (liquidity=="BID" or whale=="ACCUMULATION"))
    if htf=="CONFLICT": decision="WAIT"; reason="HTF_CONFLICT"
    elif news in ("HIGH","CRITICAL"): decision="WAIT"; reason="EVENT_RISK"
    elif overextended: decision="WAIT"; reason="AVOID_CHASING_EXTENDED_MOVE"
    elif opposition: decision="WAIT"; reason="CONTEXT_OPPOSES_TREND"
    elif bullish: decision="LONG"; reason="TREND_WITHOUT_CONTEXT_BLOCKER"
    elif bearish: decision="SHORT"; reason="TREND_WITHOUT_CONTEXT_BLOCKER"
    else: decision="WAIT"; reason="NO_DIRECTIONAL_EDGE"

    return {
      "version":VERSION,"mode":"SHADOW_CHALLENGER","decision":decision,"reason":reason,
      "evidence":evidence,"pressures":pressures,"overextended":overextended,
      "comparison_horizons_h":[4,8,12],
      "requires_cost_adjusted_evaluation":True,
      "can_override_canonical_decision":False,"can_change_score":False,
      "can_change_threshold":False,"can_change_geometry":False,
      "analysis_only":True,"live_execution":False,
    }
