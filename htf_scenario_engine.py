"""Conditional 4-12H scenario engine for ATLAS.

This layer converts the existing HTF structural thesis + HTF price-action
context into explicit conditional bullish/bearish paths. It is analysis-only:
it cannot alter Production score/threshold, qualification, actionable decision,
or enable live execution.
"""
from __future__ import annotations

VERSION = "HTF_SCENARIO_ENGINE_V1"
READINESS_CLASSIFICATION_VERSION = "HTF_SCENARIO_READINESS_STAGES_V1"
PRODUCT_HORIZON = "4-12H"


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _zone_price(zone, key, fallback=None):
    if not isinstance(zone, dict):
        return fallback
    return _f(zone.get(key), fallback)


def _frame(pa, tf):
    return ((pa or {}).get("frames") or {}).get(tf) or {}


def _bull_case(pa4, pa12):
    r4 = pa4.get("nearest_resistance_zone") or {}; s4 = pa4.get("nearest_support_zone") or {}
    r12 = pa12.get("nearest_resistance_zone") or {}; s12 = pa12.get("nearest_support_zone") or {}
    return {"direction":"LONG","trigger_type":"BREAKOUT_RETEST_HOLD","trigger_level":_zone_price(r4,"high",_zone_price(r12,"high")),"trigger_condition":"4H close above resistance, then retest holds while 12H thesis does not turn bearish","confirmation":["4H_BOS_UP_OR_BULLISH_RETEST","12H_NOT_BEARISH","NO_HIGH_SWEEP_REJECTION"],"invalidation_level":_zone_price(s4,"low",_zone_price(s12,"low")),"invalidation_condition":"4H closes back below structural support or 4H+12H thesis loses bullish alignment"}


def _bear_case(pa4, pa12):
    r4 = pa4.get("nearest_resistance_zone") or {}; s4 = pa4.get("nearest_support_zone") or {}
    r12 = pa12.get("nearest_resistance_zone") or {}; s12 = pa12.get("nearest_support_zone") or {}
    return {"direction":"SHORT","trigger_type":"BREAKDOWN_RETEST_FAIL","trigger_level":_zone_price(s4,"low",_zone_price(s12,"low")),"trigger_condition":"4H close below support, then failed retest while 12H thesis does not turn bullish","confirmation":["4H_BOS_DOWN_OR_BEARISH_RETEST","12H_NOT_BULLISH","NO_LOW_SWEEP_RECLAIM"],"invalidation_level":_zone_price(r4,"high",_zone_price(r12,"high")),"invalidation_condition":"4H closes back above structural resistance or 4H+12H thesis loses bearish alignment"}


def build_scenario_from_context(thesis, price_action):
    thesis = thesis or {}; pa = price_action or {}; pa4 = _frame(pa,"4h"); pa12 = _frame(pa,"12h")
    combined = (pa.get("combined") or {}).get("status"); thesis_status = thesis.get("status"); thesis_direction = thesis.get("direction")
    bull = _bull_case(pa4,pa12); bear = _bear_case(pa4,pa12)
    conflict = combined == "HTF_PRICE_ACTION_CONFLICT"; thesis_ready = thesis_status == "PASS" and thesis_direction in ("LONG","SHORT")
    pa_bull = combined == "BULLISH_CONFLUENCE"; pa_bear = combined == "BEARISH_CONFLUENCE"
    matching_pa = (thesis_direction == "LONG" and pa_bull) or (thesis_direction == "SHORT" and pa_bear)

    if not thesis_ready:
        preferred="WAIT"; readiness="WAIT_FOR_HTF_ALIGNMENT"; stage="WAIT"; reason=thesis.get("reason") or "HTF_THESIS_NOT_READY"
    elif conflict:
        preferred="WAIT"; readiness="WAIT_FOR_PRICE_ACTION_RESOLUTION"; stage="WAIT"; reason="HTF_PRICE_ACTION_CONFLICT"
    elif thesis_direction == "LONG" and pa_bear:
        preferred="WAIT"; readiness="WAIT_FOR_PRICE_ACTION_RESOLUTION"; stage="WAIT"; reason="BEARISH_PRICE_ACTION_OPPOSES_LONG_THESIS"
    elif thesis_direction == "SHORT" and pa_bull:
        preferred="WAIT"; readiness="WAIT_FOR_PRICE_ACTION_RESOLUTION"; stage="WAIT"; reason="BULLISH_PRICE_ACTION_OPPOSES_SHORT_THESIS"
    elif matching_pa:
        preferred=thesis_direction; readiness="CONDITIONAL_SCENARIO_READY"; stage="ARMED"; reason="HTF_THESIS_AND_PRICE_ACTION_CONFIRMED"
    else:
        preferred=thesis_direction; readiness="WATCH_SCENARIO"; stage="WATCH"; reason="HTF_THESIS_VALID_PRICE_ACTION_NOT_CONFIRMED"

    selected = bull if preferred == "LONG" else bear if preferred == "SHORT" else None
    return {"version":VERSION,"readiness_classification_version":READINESS_CLASSIFICATION_VERSION,"product_horizon":PRODUCT_HORIZON,"preferred_direction":preferred,"readiness":readiness,"scenario_stage":stage,"reason":reason,"htf_thesis_status":thesis_status,"htf_thesis_direction":thesis_direction,"price_action_status":combined,"price_action_confirmation_required":True,"price_action_confirmed":bool(matching_pa),"bull_case":bull,"bear_case":bear,"selected_case":selected,"decision_rule":"WATCH when HTF thesis is valid but matching price action is absent; ARMED only when matching HTF price-action confluence exists. LONG/SHORT remains conditional until its trigger confirms; otherwise WAIT.","can_change_score":False,"can_change_threshold":False,"can_override_canonical_decision":False,"can_mark_trade_ready":False,"forward_evidence_required_before_promotion":True,"analysis_only":True,"live_execution":False}


def install(atlas):
    if getattr(atlas,"_HTF_SCENARIO_ENGINE_INSTALLED",False): return getattr(atlas,"HTF_SCENARIO_ENGINE_STATE",{"enabled":True,"version":VERSION})
    original=atlas.production_decision
    def wrapped(symbol):
        row=original(symbol)
        if not isinstance(row,dict) or not row.get("ok"): return row
        before={"score":row.get("score"),"threshold":row.get("threshold"),"actionable_decision":row.get("actionable_decision"),"analysis_ready":row.get("analysis_ready"),"setup_ready":row.get("setup_ready")}
        scenario=build_scenario_from_context(row.get("htf_thesis"),row.get("htf_price_action")); row["htf_scenario_engine"]=scenario; row["htf_scenario_engine_version"]=VERSION
        matrix=dict(row.get("timeframe_matrix") or {}); matrix["htf_scenario_engine"]=scenario; row["timeframe_matrix"]=matrix
        plan=dict(row.get("trade_plan") or {}); plan["conditional_scenario"]=scenario.get("selected_case"); plan["bull_case"]=scenario.get("bull_case"); plan["bear_case"]=scenario.get("bear_case"); plan["scenario_readiness"]=scenario.get("readiness"); plan["scenario_stage"]=scenario.get("scenario_stage"); plan["scenario_reason"]=scenario.get("reason"); row["trade_plan"]=plan
        row["htf_scenario_score_preserved"]=row.get("score")==before["score"]; row["htf_scenario_threshold_preserved"]=row.get("threshold")==before["threshold"]; row["htf_scenario_decision_preserved"]=row.get("actionable_decision")==before["actionable_decision"]; row["htf_scenario_readiness_preserved"]=(row.get("analysis_ready")==before["analysis_ready"] and row.get("setup_ready")==before["setup_ready"])
        return row
    atlas.production_decision=wrapped; atlas._HTF_SCENARIO_ENGINE_INSTALLED=True
    atlas.HTF_SCENARIO_ENGINE_STATE={"enabled":True,"version":VERSION,"readiness_classification_version":READINESS_CLASSIFICATION_VERSION,"product_horizon":PRODUCT_HORIZON,"uses":["htf_thesis","htf_price_action"],"score_threshold_unchanged":True,"canonical_decision_override":False,"can_mark_trade_ready":False,"forward_evidence_required_before_promotion":True,"analysis_only":True,"live_execution":False}
    return atlas.HTF_SCENARIO_ENGINE_STATE
