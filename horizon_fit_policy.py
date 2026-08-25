"""ATLAS horizon-fit policy.

Research lanes are horizon-aware; Production qualification is immutable here.
Historical replay showed the recorded directional edge was weak at 1-3h and
materially stronger at 12h, so near-threshold candidates are routed to Swing
Watch instead of being promoted into Quick merely for being close to score 68.
"""

VERSION = 'HORIZON_FIT_POLICY_V1'
QUICK_SCORE_GAP_MAX = 4.0
SWING_RESEARCH_SCORE_GAP_MAX = 8.0


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def classify(*, direction, score, threshold, votes, relative_volume,
             tactical_rr=None, breakout_confirmed=False,
             production_qualified=False, execution_ready=False):
    """Return independent Quick and Swing research classifications.

    This function never changes the Production score, threshold, geometry gate,
    qualification, or actionable decision.
    """
    direction = str(direction or '').upper()
    score = _f(score)
    threshold = _f(threshold, 68.0)
    votes = int(_f(votes, 0) or 0)
    rv = _f(relative_volume, 0.0) or 0.0
    trr = _f(tactical_rr)
    has_direction = direction in ('LONG', 'SHORT')
    gap = None if score is None else round(threshold - score, 3)

    quick_confirmed = bool(
        has_direction and not production_qualified and score is not None and
        score >= threshold - QUICK_SCORE_GAP_MAX and votes >= 4 and
        breakout_confirmed and rv >= 0.80 and trr is not None and trr >= 1.0
    )
    if quick_confirmed:
        quick = {
            'status': 'QUICK_TRADE_SHADOW', 'direction': direction,
            'horizon': '1-3H', 'reason': 'STRICT_BREAKOUT_CONFIRMATION',
            'evaluation_horizons': ['1h', '3h'], 'shadow_only': True,
            'can_override_production': False,
        }
    elif has_direction:
        quick = {
            'status': 'WATCH_ONLY', 'direction': direction,
            'horizon': '1-3H', 'reason': 'QUICK_EDGE_NOT_CONFIRMED',
            'evaluation_horizons': ['1h', '3h'], 'shadow_only': True,
            'can_override_production': False,
        }
    else:
        quick = {
            'status': 'NO_SETUP', 'direction': None, 'horizon': '1-3H',
            'reason': 'NO_DIRECTION', 'evaluation_horizons': ['1h', '3h'],
            'shadow_only': True, 'can_override_production': False,
        }

    if execution_ready and production_qualified and has_direction:
        swing_status = 'SWING_PRODUCTION_READY'
        swing_reason = 'PRODUCTION_SCORE_AND_GEOMETRY_PASSED'
    elif production_qualified and has_direction:
        swing_status = 'SWING_PRODUCTION_ARMED'
        swing_reason = 'PRODUCTION_SCORE_PASSED_EXECUTION_NOT_READY'
    elif has_direction and score is not None and score >= threshold - SWING_RESEARCH_SCORE_GAP_MAX:
        swing_status = 'SWING_RESEARCH_WATCH'
        swing_reason = 'NEAR_THRESHOLD_EDGE_BELONGS_TO_12_24H_RESEARCH_LANE'
    elif has_direction:
        swing_status = 'SWING_WATCH'
        swing_reason = 'DIRECTION_EXISTS_BUT_NOT_NEAR_PRODUCTION_THRESHOLD'
    else:
        swing_status = 'NO_SETUP'
        swing_reason = 'NO_DIRECTION'

    swing = {
        'status': swing_status, 'direction': direction if has_direction else None,
        'horizon': '12-24H', 'reason': swing_reason,
        'evaluation_horizons': ['12h', '24h'], 'score': score,
        'threshold': threshold, 'score_gap_to_production': gap,
        'production_qualified': bool(production_qualified),
        'execution_ready': bool(execution_ready), 'research_only': True,
        'can_override_production': False,
    }

    preferred = 'SWING_12_24H' if swing_status in (
        'SWING_RESEARCH_WATCH', 'SWING_PRODUCTION_ARMED', 'SWING_PRODUCTION_READY'
    ) else 'QUICK_1_3H' if quick_confirmed else 'NONE'
    return {
        'version': VERSION,
        'preferred_horizon': preferred,
        'quick': quick,
        'swing': swing,
        'production_threshold_changed': False,
        'production_override_allowed': False,
    }
