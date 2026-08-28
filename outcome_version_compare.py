"""Read-only ATLAS outcome cohort comparator.

This module never promotes a scoring model and never changes Production. It only
compares already-frozen outcome cohorts and reports whether the evidence is
large enough to interpret. Promotion remains a separate explicit decision.
"""

DEFAULT_MIN_DECISIVE = 30


def _num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _cohort(summary, version):
    return ((summary or {}).get('by_scoring_version') or {}).get(str(version))


def compare_scoring_versions(summary, candidate_version, baseline_version, min_decisive=DEFAULT_MIN_DECISIVE):
    candidate = _cohort(summary, candidate_version)
    baseline = _cohort(summary, baseline_version)
    result = {
        'schema': 'ATLAS_SCORING_VERSION_COMPARISON_V1',
        'candidate_version': str(candidate_version),
        'baseline_version': str(baseline_version),
        'min_decisive_per_cohort': int(min_decisive),
        'research_only': True,
        'production_changed': False,
        'promotion_decision': 'NOT_AUTOMATED',
    }
    if candidate is None or baseline is None:
        missing = []
        if candidate is None:
            missing.append(str(candidate_version))
        if baseline is None:
            missing.append(str(baseline_version))
        return {**result, 'status': 'MISSING_COHORT', 'missing_versions': missing}

    candidate_decisive = int(candidate.get('wins') or 0) + int(candidate.get('losses') or 0)
    baseline_decisive = int(baseline.get('wins') or 0) + int(baseline.get('losses') or 0)
    candidate_wr = _num(candidate.get('win_rate_pct'))
    baseline_wr = _num(baseline.get('win_rate_pct'))
    candidate_avg = _num(candidate.get('average_directional_return_pct'))
    baseline_avg = _num(baseline.get('average_directional_return_pct'))

    evidence = {
        'candidate': {
            'total': int(candidate.get('total') or 0),
            'decisive': candidate_decisive,
            'win_rate_pct': candidate_wr,
            'average_directional_return_pct': candidate_avg,
        },
        'baseline': {
            'total': int(baseline.get('total') or 0),
            'decisive': baseline_decisive,
            'win_rate_pct': baseline_wr,
            'average_directional_return_pct': baseline_avg,
        },
        'win_rate_lift_pp': round(candidate_wr - baseline_wr, 4) if candidate_wr is not None and baseline_wr is not None else None,
        'average_directional_return_lift_pct': round(candidate_avg - baseline_avg, 6) if candidate_avg is not None and baseline_avg is not None else None,
    }

    if candidate_decisive < int(min_decisive) or baseline_decisive < int(min_decisive):
        return {
            **result,
            'status': 'INSUFFICIENT_SAMPLE',
            'evidence': evidence,
            'reason': 'Both cohorts must reach the configured decisive-sample floor before comparative interpretation.',
        }

    if None in (candidate_wr, baseline_wr, candidate_avg, baseline_avg):
        return {
            **result,
            'status': 'INCOMPLETE_METRICS',
            'evidence': evidence,
            'reason': 'Closed decisive outcomes exist but one or more comparison metrics are unavailable.',
        }

    better_win_rate = candidate_wr > baseline_wr
    better_average_return = candidate_avg > baseline_avg
    if better_win_rate and better_average_return:
        interpretation = 'CANDIDATE_LEADS_BOTH_METRICS'
    elif not better_win_rate and not better_average_return:
        interpretation = 'BASELINE_LEADS_BOTH_METRICS'
    else:
        interpretation = 'MIXED_EVIDENCE'

    return {
        **result,
        'status': 'COMPARABLE',
        'evidence': evidence,
        'interpretation': interpretation,
        'reason': 'Descriptive comparison only; no statistical significance or Production promotion is implied.',
    }
