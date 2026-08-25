import profit_engine_walkforward as wf


def obs(i, ready=False, research=False):
    return {
        'schema': 'ATLAS_PROFIT_ENGINE_OBSERVATION_V1',
        'forward_id': f'id-{i}',
        'forward_captured_at_ms': i * 1000,
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'production_signal_qualified': not research,
        'research_sample': research,
        'profit_engine': {
            'profit_ready': ready,
            'blockers': [] if ready else ['CALIBRATION_WARMUP'],
            'net_expected_r': .2 if ready else None,
            'probability': {'p_win': .65 if ready else None, 'samples': 120 if ready else 20},
        },
        'market_regime': {'asset_regime': 'TREND_UP', 'btc_regime': 'TREND_UP'},
        'execution_cost': {'validated': ready},
    }


def settlement(i, outcome='WIN_TP2', r=1.5):
    return {'id': f'id-{i}', 'path_outcome': outcome, 'r_multiple': r}


def test_join_uses_forward_id_and_excludes_unresolved():
    observations = [obs(1, True), obs(2, True), obs(3, True)]
    settlements = [settlement(1), settlement(2, 'LOSS', -1), {'id': 'id-3', 'path_outcome': 'OPEN', 'r_multiple': None}]
    joined = wf.join_frozen_to_settlements(observations, settlements)
    assert [x['forward_id'] for x in joined] == ['id-1', 'id-2']
    assert joined[0]['profit_ready'] is True


def test_research_observations_never_enter_report():
    observations = [obs(1, True), obs(2, True, research=True)]
    settlements = [settlement(1), settlement(2)]
    out = wf.report(observations, settlements)
    assert out['frozen_observations'] == 1
    assert out['settled_joined'] == 1
    assert out['research_samples_included'] is False


def test_small_sample_remains_collecting():
    observations = [obs(i, ready=True) for i in range(1, 11)]
    settlements = [settlement(i) for i in range(1, 11)]
    out = wf.report(observations, settlements)
    assert out['status'] == 'COLLECTING'
    assert 'INSUFFICIENT_SETTLED_FROZEN_OBSERVATIONS' in out['blockers']
    assert 'INSUFFICIENT_PROFIT_READY_SETTLED_OBSERVATIONS' in out['blockers']
    assert out['improves_production_expectancy'] is False


def test_validator_can_detect_stable_improvement_without_hindsight():
    observations = []
    settlements = []
    # 60 chronological observations. Production baseline alternates wins/losses;
    # the frozen Profit Engine accepts five good rows in each 20-row fold.
    for i in range(1, 61):
        position = (i - 1) % 20
        ready = position < 5
        observations.append(obs(i, ready=ready))
        if ready:
            settlements.append(settlement(i, 'WIN_TP2', 1.5))
        elif i % 2 == 0:
            settlements.append(settlement(i, 'LOSS', -1.0))
        else:
            settlements.append(settlement(i, 'WIN_TP2', 1.0))
    out = wf.report(observations, settlements)
    assert out['status'] == 'VALIDATION_READ_AVAILABLE'
    assert out['profit_ready_settled'] == 15
    assert out['stable_folds'] == 3
    assert out['folds_with_expectancy_improvement'] == 3
    assert out['delta_average_r'] > 0
    assert out['improves_production_expectancy'] is True
    assert out['hindsight_recomputation_allowed'] is False
