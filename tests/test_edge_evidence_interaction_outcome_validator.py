import copy

import edge_evidence_interaction_outcome_validator as validator
import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules


def joint():
    return {
        'report': {
            'version': 'J',
            'status': 'DESIGN_READ_AVAILABLE',
            'future_interaction_validation_supported': True,
            'horizons_with_sufficient_joint_coverage_h': [1, 4, 12],
        }
    }


def auth():
    p = protocol.build_manifest(joint())
    r = rules.build_manifest(p)
    g = {'status': 'VALIDATOR_ARMED'}
    return p, g, r


def feature_rows(n=60, candidate_ids=None):
    candidate_ids = set(candidate_ids or [])
    profit = []
    micro = []
    vol = []
    for i in range(n):
        fid = f'F{i:03d}'
        candidate = fid in candidate_ids
        common = {
            'forward_id': fid,
            'production_signal_qualified': True,
            'research_sample': False,
            'forward_captured_at_ms': 1_000_000 + i,
        }
        profit.append({
            **common,
            'profit_engine': {
                'regime_gate': {
                    'reason': 'REGIME_ALIGNED' if candidate else 'REGIME_NOT_ALIGNED'
                }
            },
        })
        micro.append({
            **common,
            'relation_to_signal': 'ALIGNED' if candidate else 'MIXED_OR_INSUFFICIENT',
        })
        fit = {
            str(h): {
                'target_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80' if candidate else 'STRETCHED_VS_EMPIRICAL_P80',
                'stop_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80' if candidate else 'TIGHT_VS_EMPIRICAL_P80',
            }
            for h in (1, 4, 12)
        }
        vol.append({**common, 'geometry_fit_by_horizon': fit})
    return profit, micro, vol


def settlements(n=60, candidate_ids=None, candidate_r=1.0, other_r=-1.0):
    candidate_ids = set(candidate_ids or [])
    rows = []
    for i in range(n):
        fid = f'F{i:03d}'
        r = candidate_r if fid in candidate_ids else other_r
        rows.append({
            'forward_id': fid,
            'captured_at_ms': 1_000_000 + i,
            'terminal': True,
            'path_outcome': 'WIN_TP2' if r > 0 else ('LOSS' if r < 0 else 'EXPIRED'),
            'r_multiple': r,
        })
    return rows


def candidates_seven_each_fold():
    # Baseline folds are F000-019, F020-039, F040-059.
    return {
        *(f'F{i:03d}' for i in range(0, 7)),
        *(f'F{i:03d}' for i in range(20, 27)),
        *(f'F{i:03d}' for i in range(40, 47)),
    }


def test_blocked_guard_prevents_outcome_loader_call():
    p, _, r = auth()
    called = {'n': 0}

    def forbidden_loader():
        called['n'] += 1
        raise AssertionError('outcomes must not be read while blocked')

    out = validator.validate(p, {'status': 'BLOCKED'}, r, [], [], [], forbidden_loader)
    assert out['status'] == 'BLOCKED'
    assert out['outcomes_read'] is False
    assert out['validator_execution_started'] is False
    assert called['n'] == 0


def test_tampered_rules_prevent_outcome_loader_call():
    p, g, r = auth()
    r['rules'][0]['microstructure_relation_to_signal_equals'] = 'OPPOSED_OR_CROWDED'
    called = {'n': 0}

    def forbidden_loader():
        called['n'] += 1
        return []

    out = validator.validate(p, g, r, [], [], [], forbidden_loader)
    assert out['status'] == 'BLOCKED'
    assert 'RULES_HASH_OR_PARENT_INVALID' in out['blockers']
    assert called['n'] == 0


def test_fixed_h1_passes_all_three_chronological_folds_without_horizon_selection():
    p, g, r = auth()
    cids = candidates_seven_each_fold()
    profit, micro, vol = feature_rows(candidate_ids=cids)
    outcome_rows = settlements(candidate_ids=cids, candidate_r=1.5, other_r=-1.0)

    out = validator.validate(p, g, r, profit, micro, vol, lambda: outcome_rows)
    assert out['status'] == 'VALIDATED_RESEARCH_ONLY'
    assert out['settled_joined_total'] == 60
    assert out['validated_research_hypothesis'] is True
    assert out['outcomes_read'] is True
    assert out['interaction_outcome_testing_performed'] is True
    assert out['horizon_selection_performed'] is False
    assert out['rule_search_performed'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    assert set(out['horizons']) == {'1', '4', '12'}
    for report in out['horizons'].values():
        assert report['candidate_total'] == 21
        assert report['baseline_total'] == 60
        assert report['validated_research_hypothesis'] is True
        assert len(report['folds']) == 3
        assert all(f['baseline']['n'] == 20 for f in report['folds'])
        assert all(f['candidate']['n'] == 7 for f in report['folds'])
        assert all(f['pass'] is True for f in report['folds'])
        assert all(f['average_r_delta_vs_baseline'] > 0 for f in report['folds'])
        assert all(f['max_drawdown_r_delta_vs_baseline'] <= 0 for f in report['folds'])


def test_one_failed_fold_cannot_be_overridden_by_other_folds_or_pooled_result():
    p, g, r = auth()
    cids = candidates_seven_each_fold()
    profit, micro, vol = feature_rows(candidate_ids=cids)
    outcome_rows = settlements(candidate_ids=cids, candidate_r=2.0, other_r=-1.0)

    # Make candidate rows in chronological fold 2 lose while non-candidates there win.
    for row in outcome_rows:
        idx = int(row['forward_id'][1:])
        if 20 <= idx < 27:
            row['r_multiple'] = -1.0
            row['path_outcome'] = 'LOSS'
        elif 27 <= idx < 40:
            row['r_multiple'] = 3.0
            row['path_outcome'] = 'WIN_TP2'

    out = validator.validate(p, g, r, profit, micro, vol, lambda: outcome_rows)
    assert out['status'] == 'FAILED_RESEARCH_HYPOTHESIS'
    assert out['validated_research_hypothesis'] is False
    for report in out['horizons'].values():
        assert report['validated_research_hypothesis'] is False
        assert report['folds'][1]['pass'] is False
        assert 'ONE_OR_MORE_FOLDS_FAILED_PREREGISTERED_CRITERIA' in report['blockers']


def test_open_ambiguous_and_missing_r_are_excluded_not_fabricated():
    p, g, r = auth()
    cids = candidates_seven_each_fold()
    profit, micro, vol = feature_rows(candidate_ids=cids)
    outcome_rows = settlements(candidate_ids=cids, candidate_r=1.5, other_r=-1.0)
    outcome_rows[0]['terminal'] = False
    outcome_rows[0]['path_outcome'] = 'OPEN'
    outcome_rows[0]['r_multiple'] = None
    outcome_rows[1]['path_outcome'] = 'AMBIGUOUS'
    outcome_rows[1]['r_multiple'] = None
    outcome_rows[2]['r_multiple'] = None

    out = validator.validate(p, g, r, profit, micro, vol, lambda: outcome_rows)
    assert out['settled_joined_total'] == 57
    assert out['excluded_settlements'] == 3
    assert out['status'] == 'COLLECTING'
    assert 'MIN_TOTAL_SETTLED_NOT_REACHED' in out['blockers']
    assert out['gate_promoted'] is False


def test_duplicate_frozen_id_fails_closed_for_interpretation():
    p, g, r = auth()
    cids = candidates_seven_each_fold()
    profit, micro, vol = feature_rows(candidate_ids=cids)
    profit.append(copy.deepcopy(profit[0]))
    out = validator.validate(p, g, r, profit, micro, vol, lambda: settlements(candidate_ids=cids))
    assert out['validated_research_hypothesis'] is False
    assert 'DUPLICATE_FROZEN_FEATURE_IDS' in out['blockers']
    assert all('DUPLICATE_FROZEN_FEATURE_IDS' in h['blockers'] for h in out['horizons'].values())
