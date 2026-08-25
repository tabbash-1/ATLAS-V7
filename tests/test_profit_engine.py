import profit_engine as pe


def base_row():
    return {
        'production_signal_qualified': True,
        'direction': 'LONG',
        'regime': 'TREND_UP',
        'entry': 100.0,
        'rr_tp2': 1.8,
    }


def test_fails_closed_without_calibration():
    out = pe.assess(base_row(), stop_loss=98.0)
    assert out['profit_ready'] is False
    assert 'CALIBRATION_WARMUP' in out['blockers']
    assert out['decision'] == 'WAIT'


def test_rejects_wrong_regime_even_with_positive_ev():
    row = base_row(); row['regime'] = 'TREND_DOWN'
    out = pe.assess(row, stop_loss=98.0, calibration={'calibrated': True, 'samples': 150, 'p_win': .65})
    assert out['profit_ready'] is False
    assert 'REGIME_NOT_ALIGNED' in out['blockers']


def test_positive_calibrated_ev_can_pass():
    out = pe.assess(
        base_row(), stop_loss=98.0,
        calibration={'calibrated': True, 'samples': 150, 'p_win': .65},
        execution={'spread_bps': 1, 'fee_bps': 2, 'slippage_bps': 1},
    )
    assert out['profit_ready'] is True
    assert out['decision'] == 'LONG'
    assert out['net_expected_r'] > pe.MIN_NET_EV_R


def test_costs_can_kill_edge():
    out = pe.assess(
        base_row(), stop_loss=99.8,
        calibration={'calibrated': True, 'samples': 150, 'p_win': .55},
        execution={'spread_bps': 10, 'fee_bps': 10, 'slippage_bps': 10},
    )
    assert out['profit_ready'] is False
    assert 'NET_EV_TOO_LOW' in out['blockers']
