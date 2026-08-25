"""ATLAS horizon-fit policy.

Research lanes are horizon-aware; Production qualification is immutable here.
Historical replay showed the recorded directional edge was weak at 1-3h and
materially stronger at 12h. Combo calibration further showed that VERY_CLOSE
is not universally positive: several LONG symbol slices are strong while some
SHORT slices are negative. These labels remain research-only.
"""

VERSION = 'HORIZON_FIT_POLICY_V3_COMBO_AWARE_SWING_PRIORITY'
QUICK_SCORE_GAP_MAX = 4.0
SWING_RESEARCH_SCORE_GAP_MAX = 8.0

# Frozen research calibration from ATLAS_HISTORICAL_SHADOW_REPLAY_V4.
# Production score/threshold/geometry are never modified by these profiles.
SWING_HIGH_PRIORITY_COMBOS = {
    'ETHUSDT|LONG|VERY_CLOSE': {'sample_12h': 20, 'positive_rate_12h_pct': 90.0, 'mean_12h_pct': 0.7187},
    'BNBUSDT|LONG|VERY_CLOSE': {'sample_12h': 18, 'positive_rate_12h_pct': 94.44, 'mean_12h_pct': 0.8522},
    'BTCUSDT|LONG|VERY_CLOSE': {'sample_12h': 17, 'positive_rate_12h_pct': 100.0, 'mean_12h_pct': 1.7511},
    'SOLUSDT|LONG|VERY_CLOSE': {'sample_12h': 15, 'positive_rate_12h_pct': 100.0, 'mean_12h_pct': 4.4434},
}
SWING_LOW_PRIORITY_COMBOS = {
    'HYPEUSDT|SHORT|VERY_CLOSE': {'sample_12h': 18, 'positive_rate_12h_pct': 22.22, 'mean_12h_pct': -2.0673},
    'DOGEUSDT|SHORT|VERY_CLOSE': {'sample_12h': 13, 'positive_rate_12h_pct': 46.15, 'mean_12h_pct': -0.8181},
}


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def classify(*, direction, score, threshold, votes, relative_volume,
             tactical_rr=None, breakout_confirmed=False,
             production_qualified=False, execution_ready=False,
             obstacle_reason=None, symbol=None):
    """Return independent Quick and Swing research classifications.

    This function never changes the Production score, threshold, geometry gate,
    qualification, or actionable decision. Calibrated combo handling only
    changes research priority labels and attaches frozen evidence.
    """
    direction = str(direction or '').upper()
    symbol = str(symbol or 'UNKNOWN').upper()
    obstacle_reason = str(obstacle_reason or 'NONE').upper()
    score = _f(score)
    threshold = _f(threshold, 68.0)
    votes = int(_f(votes, 0) or 0)
    rv = _f(relative_volume, 0.0) or 0.0
    trr = _f(tactical_rr)
    has_direction = direction in ('LONG', 'SHORT')
    gap = None if score is None else round(threshold - score, 3)
    combo = f'{symbol}|{direction}|{obstacle_reason}'

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

    near_swing_threshold = bool(
        has_direction and score is not None and
        score >= threshold - SWING_RESEARCH_SCORE_GAP_MAX
    )
    high_evidence = SWING_HIGH_PRIORITY_COMBOS.get(combo)
    low_evidence = SWING_LOW_PRIORITY_COMBOS.get(combo)

    if execution_ready and production_qualified and has_direction:
        swing_status = 'SWING_PRODUCTION_READY'
        swing_reason = 'PRODUCTION_SCORE_AND_GEOMETRY_PASSED'
        quality_tier = 'PRODUCTION'
        quality_evidence = None
    elif production_qualified and has_direction:
        swing_status = 'SWING_PRODUCTION_ARMED'
        swing_reason = 'PRODUCTION_SCORE_PASSED_EXECUTION_NOT_READY'
        quality_tier = 'PRODUCTION'
        quality_evidence = None
    elif near_swing_threshold and high_evidence:
        swing_status = 'SWING_RESEARCH_PRIORITY_HIGH'
        swing_reason = 'COMBO_CALIBRATED_POSITIVE_12H_EDGE_RESEARCH_ONLY'
        quality_tier = 'HIGH'
        quality_evidence = dict(high_evidence)
    elif near_swing_threshold and low_evidence:
        swing_status = 'SWING_RESEARCH_DEPRIORITIZED'
        swing_reason = 'COMBO_CALIBRATED_NEGATIVE_12H_EDGE_RESEARCH_ONLY'
        quality_tier = 'LOW'
        quality_evidence = dict(low_evidence)
    elif near_swing_threshold:
        swing_status = 'SWING_RESEARCH_WATCH'
        swing_reason = 'NEAR_THRESHOLD_EDGE_BELONGS_TO_12_24H_RESEARCH_LANE'
        quality_tier = 'NEUTRAL'
        quality_evidence = None
    elif has_direction:
        swing_status = 'SWING_WATCH'
        swing_reason = 'DIRECTION_EXISTS_BUT_NOT_NEAR_PRODUCTION_THRESHOLD'
        quality_tier = 'UNRATED'
        quality_evidence = None
    else:
        swing_status = 'NO_SETUP'
        swing_reason = 'NO_DIRECTION'
        quality_tier = 'NONE'
        quality_evidence = None

    swing = {
        'status': swing_status, 'direction': direction if has_direction else None,
        'horizon': '12-24H', 'reason': swing_reason,
        'evaluation_horizons': ['12h', '24h'], 'score': score,
        'threshold': threshold, 'score_gap_to_production': gap,
        'symbol': symbol, 'obstacle_reason': obstacle_reason, 'calibration_combo': combo,
        'swing_quality_tier': quality_tier,
        'swing_quality_evidence': quality_evidence,
        'production_qualified': bool(production_qualified),
        'execution_ready': bool(execution_ready), 'research_only': True,
        'can_override_production': False,
        'production_score_adjustment': 0,
    }

    preferred = 'SWING_12_24H' if swing_status in (
        'SWING_RESEARCH_PRIORITY_HIGH', 'SWING_RESEARCH_DEPRIORITIZED',
        'SWING_RESEARCH_WATCH', 'SWING_PRODUCTION_ARMED', 'SWING_PRODUCTION_READY'
    ) else 'QUICK_1_3H' if quick_confirmed else 'NONE'
    return {
        'version': VERSION,
        'preferred_horizon': preferred,
        'quick': quick,
        'swing': swing,
        'production_threshold_changed': False,
        'production_override_allowed': False,
        'production_score_adjustment': 0,
    }
