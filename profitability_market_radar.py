"""ATLAS Profitability Market Radar V1.

Ranks existing canonical Production decisions by *opportunity readiness*.
It does not create trades, alter scores/thresholds, or override FINAL_TRADE_GATE.
The purpose is to surface movement early (WATCH/ARMED) so Production can focus
deep analysis on the strongest emerging candidates instead of treating WAIT as
an undifferentiated state.
"""
from __future__ import annotations

VERSION = "ATLAS_PROFITABILITY_PIPELINE_V2"\nUP_REGIMES = {"TREND_UP","BREAKOUT_UP","VOLATILITY_EXPANSION_UP"}\nDOWN_REGIMES = {"TREND_DOWN","BREAKDOWN_DOWN","VOLATILITY_EXPANSION_DOWN"}
STATE_WEIGHT = {"ACTIONABLE": 100.0, "ARMED": 72.0, "WATCH": 48.0, "NO_SETUP": 0.0}

def _f(v, default=0.0):
    try: return float(v)
    except (TypeError, ValueError): return default

def _regime_alignment(direction, asset_regime=None, btc_regime=None):\n    d=str(direction or "").upper(); a=str(asset_regime or "").upper(); b=str(btc_regime or "").upper()\n    expected=UP_REGIMES if d=="LONG" else DOWN_REGIMES if d=="SHORT" else set()\n    if not expected: return "UNKNOWN"\n    if a in expected and b in expected: return "ALIGNED"\n    if (a and a not in expected) or (b and b not in expected): return "OPPOSED"\n    return "UNKNOWN"\n\ndef rank_row(row):
    r = row or {}
    state = str(r.get("opportunity_state") or "NO_SETUP").upper()
    score = _f(r.get("score"))
    threshold = max(1.0, _f(r.get("threshold"), 68.0))
    rr = _f(r.get("rr_tp2"))
    base = STATE_WEIGHT.get(state, 0.0)
    score_readiness = min(20.0, max(0.0, score / threshold * 20.0))
    geometry_credit = 4.0 if r.get("geometry_valid") else 0.0
    rr_credit = min(4.0, max(0.0, rr / 2.0 * 4.0))
    execution_credit = 2.0 if r.get("execution_ready") else 0.0
    alignment=_regime_alignment(r.get("direction"), r.get("asset_regime"), r.get("btc_regime"))\n    regime_credit = 4.0 if alignment=="ALIGNED" else -8.0 if alignment=="OPPOSED" else 0.0\n    radar_score = min(100.0, max(0.0, base + score_readiness + geometry_credit + rr_credit + execution_credit + regime_credit))
    return {
        "symbol": r.get("symbol"), "direction": r.get("direction"),
        "opportunity_state": state, "radar_score": round(radar_score, 2),
        "production_score": score, "production_threshold": threshold,
        "rr_tp2": rr or None, "reason": r.get("reason"),
        "action": r.get("action", "WAIT"), "regime_alignment": alignment,\n        "entry_state": "TRIGGERED" if state=="ACTIONABLE" else "ARMED" if state=="ARMED" else "WATCH" if state=="WATCH" else "NO_SETUP",
    }

def build(rows, top_n=5):
    ranked = [rank_row(x) for x in (rows or [])]
    ranked.sort(key=lambda x: (-x["radar_score"], str(x.get("symbol") or "")))
    emerging = [x for x in ranked if x["opportunity_state"] in {"WATCH","ARMED","ACTIONABLE"}]
    return {
        "schema": VERSION,
        "top_candidates": emerging[:top_n],\n        "opportunity_ranking": [{"rank":i+1, **x} for i,x in enumerate(emerging[:top_n])],
        "ranked_universe": ranked,
        "summary": {
            "assets": len(ranked),
            "emerging": len(emerging),
            "actionable": sum(x["opportunity_state"]=="ACTIONABLE" for x in ranked),
            "armed": sum(x["opportunity_state"]=="ARMED" for x in ranked),
            "watch": sum(x["opportunity_state"]=="WATCH" for x in ranked),
        },
        "safety": {
            "research_only": True, "live_execution": False,
            "can_create_trade": False, "can_override_production": False,
            "can_change_threshold": False, "decision_source_of_truth": "FINAL_TRADE_GATE",
        },
    }
