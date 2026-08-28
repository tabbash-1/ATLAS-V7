import outcome_version_compare as compare


def summary(v6, v7):
    return {'by_scoring_version': {'V6': v6, 'V7': v7}}


def cohort(wins, losses, avg, total=None):
    return {
        'total': total if total is not None else wins + losses,
        'wins': wins,
        'losses': losses,
        'win_rate_pct': round(100 * wins / (wins + losses), 2) if wins + losses else None,
        'average_directional_return_pct': avg,
    }


def test_missing_cohort_is_explicit():
    x = compare.compare_scoring_versions({'by_scoring_version': {'V6': cohort(20, 10, 0.5)}}, 'V7', 'V6')
    assert x['status'] == 'MISSING_COHORT'
    assert x['production_changed'] is False


def test_insufficient_sample_never_claims_comparability():
    x = compare.compare_scoring_versions(summary(cohort(15, 10, 0.3), cohort(20, 5, 0.8)), 'V7', 'V6')
    assert x['status'] == 'INSUFFICIENT_SAMPLE'
    assert x['promotion_decision'] == 'NOT_AUTOMATED'


def test_comparable_candidate_leads_both_metrics():
    x = compare.compare_scoring_versions(summary(cohort(18, 12, 0.2), cohort(22, 8, 0.7)), 'V7', 'V6')
    assert x['status'] == 'COMPARABLE'
    assert x['interpretation'] == 'CANDIDATE_LEADS_BOTH_METRICS'
    assert x['evidence']['win_rate_lift_pp'] > 0
    assert x['evidence']['average_directional_return_lift_pct'] == 0.5


def test_mixed_evidence_is_not_promoted():
    x = compare.compare_scoring_versions(summary(cohort(20, 10, 0.8), cohort(21, 9, 0.4)), 'V7', 'V6')
    assert x['status'] == 'COMPARABLE'
    assert x['interpretation'] == 'MIXED_EVIDENCE'
    assert x['promotion_decision'] == 'NOT_AUTOMATED'


if __name__ == '__main__':
    test_missing_cohort_is_explicit()
    test_insufficient_sample_never_claims_comparability()
    test_comparable_candidate_leads_both_metrics()
    test_mixed_evidence_is_not_promoted()
    print('outcome version compare tests: ok')
