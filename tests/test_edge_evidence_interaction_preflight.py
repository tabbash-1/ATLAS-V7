import copy

import edge_evidence_interaction_preflight as preflight
import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules
import edge_evidence_interaction_validator_guard as guard


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
    g = guard.evaluate(p, joint())
    assert g['status'] == 'VALIDATOR_ARMED'
    return p, g, r


def features(n=60, candidate_ids=None, include_research=False):
    candidate_ids = set(candidate_ids or [])
    profit, micro, vol = [], [], []
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
            'profit_engine': {'regime_gate': {'reason': 'REGIME_ALIGNED' if candidate else 'REGIME_NOT_ALIGNED'}},
        })
        micro.append({**common, 'relation_to_signal': 'ALIGNED' if candidate else 'MIXED_OR_INSUFFICIENT'})
        vol.append({
            **common,
            'geometry_fit_by_horizon': {
                str(h): {
                    'target_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80' if candidate else 'STRETCHED_VS_EMPIRICAL_P80',
                    'stop_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80' if candidate else 'TIGHT_VS_EMPIRICAL_P80',
                }
                for h in (1, 4, 12)
            },
        })

    if include_research:
        research = {
            'forward_id': 'RESEARCH-1',
            'production_signal_qualified': True,
            'research_sample': True,
            'profit_engine': {'regime_gate': {'reason': 'REGIME_ALIGNED'}},
        }
        profit.append(research)
        micro.append({**research, 'relation_to_signal': 'ALIGNED'})
        vol.append({
            **research,
            'geometry_fit_by_horizon': {
                str(h): {
                    'target_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80',
                    'stop_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80',
                }
                for h in (1, 4, 12)
            },
        })
    return profit, micro, vol


def candidate_ids(n=20):
    return {f'F{i:03d}' for i in range(n)}


def test_less_than_sixty_common_frozen_rows_blocks_outcome_access():
    p, g, r = auth()
    profit, micro, vol = features(n=59, candidate_ids=candidate_ids(20))
    out = preflight.evaluate(p, g, r, profit, micro, vol)
    assert out['status'] == 'COLLECTING_PRE_OUTCOME'
    assert out['outcome_access_allowed'] is False
    assert out['outcomes_read'] is False
    assert out['matched_frozen_total'] == 59
    assert 'MIN_FROZEN_COMMON_COHORT_NOT_REACHED' in out['blockers']


def test_less_than_twenty_h1_candidates_blocks_outcome_access():
    p, g, r = auth()
    profit, micro, vol = features(n=60, candidate_ids=candidate_ids(19))
    out = preflight.evaluate(p, g, r, profit, micro, vol)
    assert out['matched_frozen_total'] == 60
    assert out['outcome_access_allowed'] is False
    assert out['candidate_frozen_by_horizon'] == {'1': 19, '4': 19, '12': 19}
    assert 'MIN_FROZEN_H1_CANDIDATES_NOT_REACHED_1H' in out['blockers']
    assert 'MIN_FROZEN_H1_CANDIDATES_NOT_REACHED_4H' in out['blockers']
    assert 'MIN_FROZEN_H1_CANDIDATES_NOT_REACHED_12H' in out['blockers']


def test_exact_minimum_common_and_candidates_all_horizons_allows_outcome_read():
    p, g, r = auth()
    profit, micro, vol = features(n=60, candidate_ids=candidate_ids(20))
    out = preflight.evaluate(p, g, r, profit, micro, vol)
    assert out['status'] == 'READY_FOR_CANONICAL_OUTCOME_READ'
    assert out['outcome_access_allowed'] is True
    assert out['outcomes_read'] is False
    assert out['matched_frozen_total'] == 60
    assert out['candidate_frozen_by_horizon'] == {'1': 20, '4': 20, '12': 20}
    assert out['blockers'] == []


def test_research_rows_do_not_increase_common_or_candidate_counts():
    p, g, r = auth()
    profit, micro, vol = features(n=59, candidate_ids=candidate_ids(19), include_research=True)
    out = preflight.evaluate(p, g, r, profit, micro, vol)
    assert out['matched_frozen_total'] == 59
    assert out['candidate_frozen_by_horizon'] == {'1': 19, '4': 19, '12': 19}
    assert out['outcome_access_allowed'] is False


def test_duplicate_frozen_feature_id_fails_closed():
    p, g, r = auth()
    profit, micro, vol = features(n=61, candidate_ids=candidate_ids(21))
    profit.append(copy.deepcopy(profit[0]))
    out = preflight.evaluate(p, g, r, profit, micro, vol)
    assert out['outcome_access_allowed'] is False
    assert 'F000' in out['duplicate_frozen_feature_ids']
    assert 'DUPLICATE_FROZEN_FEATURE_IDS' in out['blockers']


def test_stale_guard_hash_blocks_before_any_sample_interpretation():
    p, g, r = auth()
    g = dict(g)
    g['armed_protocol_hash'] = 'stale'
    profit, micro, vol = features(n=60, candidate_ids=candidate_ids(20))
    out = preflight.evaluate(p, g, r, profit, micro, vol)
    assert out['status'] == 'BLOCKED'
    assert out['outcome_access_allowed'] is False
    assert out['matched_frozen_total'] == 0
    assert 'GUARD_PROTOCOL_HASH_MISMATCH' in out['blockers']
