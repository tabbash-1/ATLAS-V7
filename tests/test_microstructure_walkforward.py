import json

import microstructure_walkforward as mw


def obs(i, relation_consensus, direction='LONG', *, qualified=True, research=False):
    return {
        'schema': 'ATLAS_MICROSTRUCTURE_OBSERVATION_V1',
        'forward_id': f'F{i}',
        'forward_captured_at_ms': 1_700_000_000_000 + i * 1000,
        'symbol': 'BTCUSDT',
        'direction': direction,
        'production_signal_qualified': qualified,
        'research_sample': research,
        'microstructure_memory': {
            'consensus': relation_consensus,
            'ready_windows': 3,
        },
    }


def settlement(i, r):
    if r is None:
        return {'id': f'F{i}', 'path_outcome': 'OPEN', 'r_multiple': None}
    return {
        'id': f'F{i}',
        'path_outcome': 'WIN_TP2' if r > 0 else 'LOSS',
        'r_multiple': r,
    }


def test_relation_mapping_is_direction_aware():
    assert mw.classify_relation('LONG', 'BULLISH_FLOW') == 'ALIGNED'
    assert mw.classify_relation('LONG', 'BEARISH_FLOW') == 'OPPOSED_OR_CROWDED'
    assert mw.classify_relation('LONG', 'LONG_CROWDING_RISK') == 'OPPOSED_OR_CROWDED'
    assert mw.classify_relation('SHORT', 'BEARISH_FLOW') == 'ALIGNED'
    assert mw.classify_relation('SHORT', 'BULLISH_FLOW') == 'OPPOSED_OR_CROWDED'
    assert mw.classify_relation('SHORT', 'SHORT_CROWDING_RISK') == 'OPPOSED_OR_CROWDED'
    assert mw.classify_relation('LONG', 'MIXED') == 'MIXED_OR_INSUFFICIENT'


def test_reader_excludes_research_and_unqualified(tmp_path):
    path = tmp_path / 'obs.jsonl'
    rows = [
        obs(1, 'BULLISH_FLOW'),
        obs(2, 'BULLISH_FLOW', qualified=False),
        obs(3, 'BULLISH_FLOW', research=True),
        {**obs(4, 'BULLISH_FLOW'), 'forward_id': None},
    ]
    path.write_text('\n'.join(json.dumps(x) for x in rows) + '\n')
    loaded = mw.read_observations(path)
    assert [x['forward_id'] for x in loaded] == ['F1']


def test_open_or_ambiguous_without_r_is_not_forced_into_ab_sample():
    observations = [obs(1, 'BULLISH_FLOW'), obs(2, 'BEARISH_FLOW')]
    joined = mw.join(observations, [settlement(1, 2.0), settlement(2, None)])
    assert len(joined) == 1
    assert joined[0]['forward_id'] == 'F1'
    assert joined[0]['r_multiple'] == 2.0


def test_small_sample_never_claims_future_gate_support():
    observations = [obs(i, 'BULLISH_FLOW' if i % 2 else 'BEARISH_FLOW') for i in range(1, 11)]
    settlements = [settlement(i, 2.0 if i % 2 else -1.0) for i in range(1, 11)]
    out = mw.report(observations, settlements)
    assert out['status'] == 'COLLECTING'
    assert out['evidence_supports_future_gate'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    assert 'INSUFFICIENT_ALIGNED_SETTLED' in out['blockers']
    assert 'INSUFFICIENT_OPPOSED_SETTLED' in out['blockers']


def test_strong_multifold_evidence_can_support_future_gate_but_never_promotes_it():
    observations = []
    settlements = []
    # Three 20-trade folds. In every fold 12 aligned trades average +2R and
    # 8 opposed trades average -1R. This deliberately exceeds global sample
    # minima and fold informativeness requirements.
    i = 1
    for _fold in range(3):
        for _ in range(12):
            observations.append(obs(i, 'BULLISH_FLOW'))
            settlements.append(settlement(i, 2.0))
            i += 1
        for _ in range(8):
            observations.append(obs(i, 'BEARISH_FLOW'))
            settlements.append(settlement(i, -1.0))
            i += 1

    out = mw.report(observations, settlements)
    assert out['status'] == 'VALIDATION_READ_AVAILABLE'
    assert out['aligned']['n'] == 36
    assert out['opposed_or_crowded']['n'] == 24
    assert out['informative_folds'] == 3
    assert out['folds_where_aligned_beats_opposed'] == 3
    assert out['aligned_average_r_delta_vs_baseline'] > 0
    assert out['opposed_average_r_delta_vs_baseline'] < 0
    assert out['evidence_supports_future_gate'] is True
    # Validation support is not permission to mutate Production.
    assert out['gate_promoted'] is False
    assert out['gate_mode'] == 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED'
    assert out['can_override_production'] is False
    assert out['hindsight_recomputation_allowed'] is False
    assert out['research_samples_included'] is False
