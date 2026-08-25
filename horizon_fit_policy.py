"""ATLAS horizon-fit policy.

Research lanes are horizon-aware; Production qualification is immutable here.
Raw snapshot replay suggested combo-specific 12h patterns, but de-correlation
showed repeated snapshots are not independent evidence. Therefore calibrated
combo labels are PROVISIONAL until enough independent 12h episodes and fresh
out-of-sample cases accumulate.
"""

VERSION = 'HORIZON_FIT_POLICY_V4_PROVISIONAL_EPISODE_AWARE'
QUICK_SCORE_GAP_MAX = 4.0
SWING_RESEARCH_SCORE_GAP_MAX = 8.0
MIN_INDEPENDENT_EPISODES_FOR_VALIDATED_TIER = 5

# Frozen provisional profiles. Each currently has only two independent 12h
# episodes after de-correlation, so none is considered validated.
SWING_PROVISIONAL_POSITIVE_COMBOS = {
    'ETHUSDT|LONG|VERY_CLOSE': {'independent_12h_n': 2, 'positive_rate_12h_pct': 100.0, 'mean_12h_pct': 1.1726},
    'BNBUSDT|LONG|VERY_CLOSE': {'independent_12h_n': 2, 'positive_rate_12h_pct': 100.0, 'mean_12h_pct': 1.0981},
    'BTCUSDT|LONG|VERY_CLOSE': {'independent_12h_n': 2, 'positive_rate_12h_pct': 100.0, 'mean_12h_pct': 1.7597},
    'SOLUSDT|LONG|VERY_CLOSE': {'independent_12h_n': 2, 'positive_rate_12h_pct': 100.0, 'mean_12h_pct': 3.4383},
}
SWING_PROVISIONAL_NEGATIVE_COMBOS = {
    'HYPEUSDT|SHORT|VERY_CLOSE': {'independent_12h_n': 2, 'positive_rate_12h_pct': 50.0, 'mean_12h_pct': -1.5549},
    'DOGEUSDT|SHORT|VERY_CLOSE': {'independent_12h_n': 2, 'positive_rate_12h_pct': 50.0, 'mean_12h_pct': -0.3284},
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
    """Return Quick and Swing research classifications without Production mutation."""
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
    positive_evidence = SWING_PROVISIONAL_POSITIVE_COMBOS.get(combo)
    negative_evidence = SWING_PROVISIONAL_NEGATIVE_COMBOS.get(combo)

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
    elif near_swing_threshold and positive_evidence:
        swing_status = 'SWING_RESEARCH_PROVISIONAL_POSITIVE'
        swing_reason = 'POSITIVE_COMBO_PATTERN_NOT_YET_INDEPENDENTLY_VALIDATED'
        quality_tier = 'PROVISIONAL_POSITIVE'
        quality_evidence = dict(positive_evidence)
    elif near_swing_threshold and negative_evidence:
        swing_status = 'SWING_RESEARCH_PROVISIONAL_NEGATIVE'
        swing_reason = 'NEGATIVE_COMBO_PATTERN_NOT_YET_INDEPENDENTLY_VALIDATED'
        quality_tier = 'PROVISIONAL_NEGATIVE'
        quality_evidence = dict(negative_evidence)
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
        'minimum_independent_episodes_for_validated_tier': MIN_INDEPENDENT_EPISODES_FOR_VALIDATED_TIER,
        'independent_validation_complete': bool(
            quality_evidence and int(quality_evidence.get('independent_12h_n') or 0) >= MIN_INDEPENDENT_EPISODES_FOR_VALIDATED_TIER
        ),
        'production_qualified': bool(production_qualified),
        'execution_ready': bool(execution_ready), 'research_only': True,
        'can_override_production': False,
        'production_score_adjustment': 0,
    }

    preferred = 'SWING_12_24H' if swing_status in (
        'SWING_RESEARCH_PROVISIONAL_POSITIVE', 'SWING_RESEARCH_PROVISIONAL_NEGATIVE',
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
