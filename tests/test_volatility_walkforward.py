import json

import volatility_walkforward as vw


def fit(category):
    if category == 'PLAUSIBLE_BOTH':
        return {
            'status': 'READY',
            'target_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80',
            'stop_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80',
            'target_to_p80_ratio': 0.9,
            'stop_to_p80_ratio': 0.6,
        }
    if category == 'STRETCHED_TARGET':
        return {
            'status': 'READY',
            'target_fit': 'STRETCHED_VS_EMPIRICAL_P80',
            'stop_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80',
            'target_to_p80_ratio': 2.1,
            'stop_to_p80_ratio': 0.6,
        }
    if category == 'TIGHT_STOP':
        return {
            'status': 'READY',
            'target_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80',
            'stop_fit': 'TIGHT_VS_EMPIRICAL_P80',
            'target_to_p80_ratio': 0.9,
            'stop_to_p80_ratio': 0.2,
        }
    if category == 'STRETCHED_TARGET+TIGHT_STOP':
        return {
            'status': 'READY',
            'target_fit': 'STRETCHED_VS_EMPIRICAL_P80',
            'stop_fit': 'TIGHT_VS_EMPIRICAL_P80',
            'target_to_p80_ratio': 2.1,
            'stop_to_p80_ratio': 0.2,
        }
    return {'status': 'INSUFFICIENT'}


def obs(i, c1='PLAUSIBLE_BOTH', c4='PLAUSIBLE_BOTH', c12='PLAUSIBLE_BOTH', *, qualified=True, research=False):
    return {
        'schema': 'ATLAS_VOLATILITY_FORECAST_OBSERVATION_V1',
        'forward_id': f'V{i}',
        'forward_captured_at_ms': 1_700_000_000_000 + i * 1000,
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'production_signal_qualified': qualified,
        'research_sample': research,
        'forecast': {'volatility_regime': 'VOL_NORMAL'},
        'geometry_fit_by_horizon': {
            '1': fit(c1), '4': fit(c4), '12': fit(c12),
        },
    }


def settlement(i, r):
    return {
        'id': f'V{i}',
        'path_outcome': 'OPEN' if r is None else ('WIN_TP2' if r > 0 else 'LOSS'),
        'r_multiple': r,
    }


def test_geometry_classifier_is_explicit():
    assert vw.classify_geometry(fit('PLAUSIBLE_BOTH')) == 'PLAUSIBLE_BOTH'
    assert vw.classify_geometry(fit('STRETCHED_TARGET')) == 'STRETCHED_TARGET'
    assert vw.classify_geometry(fit('TIGHT_STOP')) == 'TIGHT_STOP'
    assert vw.classify_geometry(fit('STRETCHED_TARGET+TIGHT_STOP')) == 'STRETCHED_TARGET+TIGHT_STOP'
    assert vw.classify_geometry({'status': 'INSUFFICIENT'}) == 'INSUFFICIENT'


def test_reader_excludes_research_unqualified_and_missing_id(tmp_path):
    path = tmp_path / 'vol.jsonl'
    rows = [
        obs(1),
        obs(2, qualified=False),
        obs(3, research=True),
        {**obs(4), 'forward_id': None},
    ]
    path.write_text('\n'.join(json.dumps(x) for x in rows) + '\n')
    loaded = vw.read_observations(path)
    assert [x['forward_id'] for x in loaded] == ['V1']


def test_open_outcomes_are_not_forced_into_performance_sample():
    joined = vw.join([obs(1), obs(2)], [settlement(1, 2.0), settlement(2, None)])
    assert len(joined) == 1
    assert joined[0]['forward_id'] == 'V1'


def test_small_sample_remains_collecting_for_all_horizons():
    observations = [obs(i, 'PLAUSIBLE_BOTH' if i % 2 else 'STRETCHED_TARGET') for i in range(1, 11)]
    settlements = [settlement(i, 2.0 if i % 2 else -1.0) for i in range(1, 11)]
    out = vw.report(observations, settlements)
    assert out['status'] == 'COLLECTING'
    assert out['horizons_supporting_future_filter'] == []
    assert out['chosen_trade_horizon_assumed'] is False
    assert out['gate_promoted'] is False
    for row in out['by_horizon'].values():
        assert row['evidence_supports_future_geometry_filter'] is False
        assert row['can_override_production'] is False


def test_only_supported_horizon_is_reported_without_assuming_trade_horizon():
    observations = []
    settlements = []
    i = 1
    # Three folds. For 4h only, each fold has 12 plausible +2R and 8 risky -1R.
    # 1h and 12h stay plausible for everyone, so they cannot form a risky cohort.
    for _fold in range(3):
        for _ in range(12):
            observations.append(obs(i, 'PLAUSIBLE_BOTH', 'PLAUSIBLE_BOTH', 'PLAUSIBLE_BOTH'))
            settlements.append(settlement(i, 2.0))
            i += 1
        for _ in range(8):
            observations.append(obs(i, 'PLAUSIBLE_BOTH', 'STRETCHED_TARGET', 'PLAUSIBLE_BOTH'))
            settlements.append(settlement(i, -1.0))
            i += 1

    out = vw.report(observations, settlements)
    four = out['by_horizon']['4']
    assert four['status'] == 'VALIDATION_READ_AVAILABLE'
    assert four['evidence_supports_future_geometry_filter'] is True
    assert four['categories']['PLAUSIBLE_BOTH']['n'] == 36
    assert four['risky_geometry_combined']['n'] == 24
    assert four['informative_folds'] == 3
    assert four['folds_where_plausible_beats_risky'] == 3
    assert four['plausible_average_r_delta_vs_baseline'] > 0
    assert four['risky_average_r_delta_vs_baseline'] < 0
    assert out['horizons_supporting_future_filter'] == [4]
    assert out['chosen_trade_horizon_assumed'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    assert out['hindsight_recomputation_allowed'] is False
    assert out['research_samples_included'] is False
