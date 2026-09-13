"""Deterministic Production opportunity readiness ranking.

This module does not alter ATLAS decisions, scores, thresholds, geometry, or
trade eligibility. It only ranks current FINAL_TRADE_GATE outputs by how many
required Production conditions are already satisfied.
"""

VERSION = "ATLAS_OPPORTUNITY_READINESS_V1"


def _blockers(decision):
    gate = decision.get("final_trade_gate") or {}
    return [str(x) for x in (gate.get("blockers") or [])]


def _has(blockers, name):
    return name in blockers


def assess(decision):
    blockers = _blockers(decision)
    gate = decision.get("final_trade_gate") or {}
    htf = decision.get("htf_thesis") or {}
    trade_ready = bool(gate.get("trade_ready"))

    checks = {
        "htf_direction_resolved": bool(decision.get("product_direction") in ("LONG", "SHORT"))
            and not _has(blockers, "HTF_PRODUCT_DIRECTION_UNRESOLVED"),
        "htf_4h_12h_aligned": not _has(blockers, "HTF_4H_12H_NOT_ALIGNED")
            and htf.get("reason") != "4H_12H_NOT_ALIGNED",
        "entry_confirmation_aligned": not _has(blockers, "ENTRY_CONFIRMATION_NOT_ALIGNED"),
        "production_score_qualified": bool(decision.get("production_signal_qualified"))
            and not _has(blockers, "PRODUCTION_SIGNAL_NOT_QUALIFIED"),
        "score_direction_matches_htf": decision.get("direction_alignment") == "ALIGNED"
            and not _has(blockers, "SCORE_DIRECTION_NOT_HTF_DIRECTION"),
        "pre_final_actionable": not _has(blockers, "PRE_FINAL_DECISION_NOT_ACTIONABLE"),
        "breakout_structure_confirmed": not _has(blockers, "BREAKOUT_STRUCTURE_NOT_CONFIRMED"),
    }
    weights = {
        "htf_direction_resolved": 20,
        "htf_4h_12h_aligned": 20,
        "entry_confirmation_aligned": 15,
        "production_score_qualified": 15,
        "score_direction_matches_htf": 10,
        "pre_final_actionable": 10,
        "breakout_structure_confirmed": 10,
    }
    readiness = 100 if trade_ready else sum(weights[k] for k, ok in checks.items() if ok)
    missing = [k for k, ok in checks.items() if not ok]
    score = decision.get("score")
    threshold = decision.get("signal_threshold")
    score_gap = None
    try:
        score_gap = max(0.0, float(threshold) - float(score))
    except Exception:
        pass

    if trade_ready:
        tier = "TRADE_READY"
    elif readiness >= 80:
        tier = "VERY_CLOSE"
    elif readiness >= 60:
        tier = "CLOSE"
    elif readiness >= 40:
        tier = "DEVELOPING"
    else:
        tier = "EARLY"

    next_required = missing[0] if missing else None
    return {
        "symbol": decision.get("symbol"),
        "actionable_decision": decision.get("actionable_decision"),
        "candidate_direction": decision.get("candidate_direction"),
        "product_direction": decision.get("product_direction"),
        "score": score,
        "signal_threshold": threshold,
        "score_gap_to_threshold": round(score_gap, 3) if score_gap is not None else None,
        "trade_ready": trade_ready,
        "readiness_score": readiness,
        "readiness_tier": tier,
        "checks": checks,
        "missing_conditions": missing,
        "next_required_condition": next_required,
        "blockers": blockers,
        "htf_status": htf.get("status"),
        "htf_reason": htf.get("reason"),
        "diagnostic_only": True,
        "readiness_score_is_probability": False,
        "can_override_production": False,
        "research_only": True,
        "live_execution": False,
    }


def install(atlas):
    def rank(symbols=None):
        universe = list(symbols or atlas.ON_DEMAND_SYMBOLS)
        rows = []
        errors = []
        for symbol in universe:
            symbol = str(symbol).upper().replace("BINANCE:", "")
            try:
                decision = atlas.production_decision(symbol)
                if not decision.get("ok"):
                    errors.append({"symbol": symbol, "error": decision.get("error") or "decision_not_ok"})
                    continue
                rows.append(assess(decision))
            except Exception as exc:
                errors.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})

        rows.sort(key=lambda row: (
            1 if row.get("trade_ready") else 0,
            row.get("readiness_score") or 0,
            1 if row.get("production_score_qualified") else 0,
            row.get("score") if row.get("score") is not None else -1,
        ), reverse=True)
        for idx, row in enumerate(rows, 1):
            row["rank"] = idx
        return {
            "ok": True,
            "version": VERSION,
            "decision_source_of_truth": "FINAL_TRADE_GATE",
            "ranking_rule": "TRADE_READY_THEN_COMPLETED_REQUIRED_GATES_THEN_SCORE",
            "threshold_changed": False,
            "score_changed": False,
            "production_decision_changed": False,
            "readiness_score_is_probability": False,
            "opportunities": rows,
            "errors": errors,
            "research_only": True,
            "live_execution": False,
        }

    atlas.opportunity_readiness = rank
    atlas.OPPORTUNITY_READINESS_VERSION = VERSION
    return {
        "enabled": True,
        "version": VERSION,
        "decision_source_of_truth": "FINAL_TRADE_GATE",
        "can_override_production": False,
        "threshold_changed": False,
        "score_changed": False,
    }
