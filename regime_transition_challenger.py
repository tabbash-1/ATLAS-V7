"""ATLAS Regime Transition Challenger V1 — research/shadow only.

Tests whether WAIT caused by HTF conflict can be resolved by independent market
regime continuity plus asset confirmation. It cannot alter Production, scores,
thresholds, geometry, or execution.
"""
from __future__ import annotations

VERSION = "ATLAS_REGIME_TRANSITION_CHALLENGER_V2_NET_RR"
LOCKED_ROUND_TRIP_COST_BPS = 16
LOCKED_FUNDING_BPS_12H = 1

UP = {"TREND_UP","BREAKOUT_UP","VOLATILITY_EXPANSION_UP"}
DOWN = {"TREND_DOWN","BREAKDOWN_DOWN","VOLATILITY_EXPANSION_DOWN"}

def _u(v): return str(v or "").strip().upper()
def _f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def assess(row, asset_regime, btc_regime, breadth=None, derivatives=None):
    row=row or {}; asset_regime=asset_regime or {}; btc_regime=btc_regime or {}
    breadth=breadth or {}; derivatives=derivatives or {}
    candidate=_u(row.get("candidate_direction") or row.get("entry_confirmation_direction"))
    canonical=_u(row.get("canonical_product_decision") or row.get("actionable_decision"))
    reason=_u(row.get("wait_reason") or row.get("actionable_reason"))
    frames=((row.get("htf_thesis") or {}).get("frames") or {})
    b1=_u((frames.get("1h") or {}).get("bias")); b4=_u((frames.get("4h") or {}).get("bias"))
    ar=_u(asset_regime.get("regime")); br=_u(btc_regime.get("regime"))
    breadth_dir=_u(breadth.get("direction")); breadth_ratio=_f(breadth.get("aligned_ratio"))
    deriv_dir=_u(derivatives.get("direction")); crowded=bool(derivatives.get("crowded",False))

    blockers=[]; evidence=[]
    if canonical!="WAIT": blockers.append("CANONICAL_NOT_WAIT")
    if "HTF" not in reason: blockers.append("NOT_HTF_CONFLICT_WAIT")
    if candidate not in {"LONG","SHORT"}: blockers.append("NO_CANDIDATE_DIRECTION")
    if b1!=candidate: blockers.append("1H_NOT_CONFIRMED")
    if b4!=candidate: blockers.append("4H_NOT_CONFIRMED")

    expected=UP if candidate=="LONG" else DOWN
    if ar not in expected: blockers.append("ASSET_REGIME_NOT_ALIGNED")
    else: evidence.append("ASSET_REGIME_ALIGNED")
    if br not in expected: blockers.append("BTC_REGIME_NOT_ALIGNED")
    else: evidence.append("BTC_REGIME_ALIGNED")

    if breadth_dir:
        if breadth_dir!=candidate: blockers.append("BREADTH_OPPOSES")
        elif breadth_ratio is not None and breadth_ratio>=0.60: evidence.append("BREADTH_ALIGNED")
        else: blockers.append("BREADTH_INSUFFICIENT")
    else: blockers.append("BREADTH_MISSING")

    if crowded: blockers.append("DERIVATIVES_CROWDED")
    elif deriv_dir:
        if deriv_dir!=candidate: blockers.append("DERIVATIVES_OPPOSE")
        else: evidence.append("DERIVATIVES_ALIGNED")
    else: evidence.append("DERIVATIVES_UNAVAILABLE_NO_CREDIT")

    geometry=((row.get("htf_core_geometry") or {}).get("ready") is True)
    rr=_f(((row.get("analyst_output") or {}).get("risk_reward")))
    if not geometry: blockers.append("GEOMETRY_NOT_READY")
    ao=row.get("analyst_output") or {}
    entry=_f(ao.get("entry")); stop=_f(ao.get("stop_loss"))
    locked_cost_bps=LOCKED_ROUND_TRIP_COST_BPS+LOCKED_FUNDING_BPS_12H
    cost_r=None; net_rr=None
    if rr is not None and entry is not None and stop is not None:
        risk=abs(entry-stop)
        if risk>0:
            cost_r=entry*(locked_cost_bps/10000.0)/risk
            net_rr=rr-cost_r
    if net_rr is None or net_rr < 2.0: blockers.append("NET_RR_BELOW_2_OR_MISSING")

    eligible=not blockers and len([x for x in evidence if not x.endswith("NO_CREDIT")])>=3
    return {
      "version":VERSION,"mode":"RESEARCH_SHADOW","decision":candidate if eligible else "WAIT",
      "eligible":eligible,"evidence":evidence,"blockers":blockers,
      "minimum_independent_confirmations":3,"product_horizon":"4-12H",
      "gross_rr":rr,"locked_cost_bps_12h":locked_cost_bps,"modeled_cost_r":cost_r,"net_rr_after_locked_cost":net_rr,
      "can_override_production":False,"can_change_threshold":False,
      "can_change_score":False,"can_change_geometry":False,
      "live_execution":False,
    }
