"""ATLAS Transition Quality V1 — prospective research only."""
VERSION="ATLAS_TRANSITION_QUALITY_V1"
UP={"TREND_UP","BREAKOUT_UP","VOLATILITY_EXPANSION_UP"}
DOWN={"TREND_DOWN","BREAKDOWN_DOWN","VOLATILITY_EXPANSION_DOWN"}
def _u(v): return str(v or "").strip().upper()
def _f(v):
    try: return float(v)
    except (TypeError,ValueError): return None
def assess(observation):
    o=observation or {}; e=o.get("frozen_evidence") or {}; candidate=_u(o.get("candidate_direction"))
    frames=e.get("frames") or {}; asset=e.get("asset_regime") or {}; btc=e.get("btc_regime") or {}
    deriv=e.get("derivatives") or {}; breadth=e.get("breadth") or {}; blockers=[]; evidence=[]
    if candidate not in {"LONG","SHORT"}: blockers.append("NO_CANDIDATE")
    expected=UP if candidate=="LONG" else DOWN
    opposite="SHORT" if candidate=="LONG" else "LONG"
    for tf in ("1h","4h"):
        if _u((frames.get(tf) or {}).get("bias"))!=candidate: blockers.append(tf.upper()+"_NOT_ALIGNED")
        else: evidence.append(tf.upper()+"_ALIGNED")
    for tf in ("12h","1d"):
        if _u((frames.get(tf) or {}).get("bias"))==opposite: blockers.append(tf.upper()+"_OPPOSES")
    if _u(asset.get("regime")) not in expected: blockers.append("ASSET_REGIME_NOT_ALIGNED")
    else: evidence.append("ASSET_REGIME_ALIGNED")
    if _u(btc.get("regime")) not in expected: blockers.append("BTC_REGIME_NOT_ALIGNED")
    else: evidence.append("BTC_REGIME_ALIGNED")
    if not deriv: blockers.append("DERIVATIVES_MISSING")
    elif bool(deriv.get("crowded")): blockers.append("DERIVATIVES_CROWDED")
    elif _u(deriv.get("direction"))!=candidate: blockers.append("DERIVATIVES_OPPOSE")
    else: evidence.append("DERIVATIVES_ALIGNED")
    ratio=_f(breadth.get("aligned_ratio"))
    if ratio is None or ratio<0.60: blockers.append("BREADTH_NOT_ALIGNED")
    else: evidence.append("BREADTH_ALIGNED")
    net_rr=_f(e.get("net_rr_after_locked_cost"))
    if net_rr is None or net_rr<2.0: blockers.append("NET_RR_BELOW_2_OR_MISSING")
    else: evidence.append("NET_RR_AT_LEAST_2")
    eligible=not blockers
    return {"version":VERSION,"decision":candidate if eligible else "WAIT","eligible":eligible,
            "evidence":evidence,"blockers":blockers,"research_only":True,"paper_only":True,
            "can_override_production":False,"live_execution":False}
