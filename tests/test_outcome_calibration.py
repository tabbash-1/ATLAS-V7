import outcome_calibration as c


def row(score, ret, direction='LONG', qualified=None, execution_ready=None, symbol='BTCUSDT'):
    x = {
        'symbol': symbol,
        'direction': direction,
        'final_score': score,
        'forward_return_pct': {'24': ret},
    }
    if qualified is not None:
        x['production_signal_qualified'] = qualified
    if execution_ready is not None:
        x['execution_ready'] = execution_ready
    return x


def test_short_return_is_direction_normalized():
    assert c.directional_return(row(70, -2.0, direction='SHORT'), 24) == 2.0


def test_score_bands_respect_threshold():
    assert c.score_band(67, 68) == '60-67'
    assert c.score_band(68, 68) == '68-74'
    assert c.score_band(82, 68) == '82+'


def test_opportunity_state_separates_watch_armed_actionable():
    assert c.opportunity_state(row(65, 1.0, qualified=False), 68) == 'WATCH'
    assert c.opportunity_state(row(70, 1.0, qualified=True, execution_ready=False), 68) == 'ARMED'
    assert c.opportunity_state(row(70, 1.0, qualified=True, execution_ready=True), 68) == 'ACTIONABLE'


def test_calibration_never_auto_applies_threshold():
    rows = []
    for i in range(40):
        rows.append(row(66, 1.0 if i < 30 else -0.5, qualified=False))
        rows.append(row(70, 0.5 if i < 24 else -0.5, qualified=True, execution_ready=True))
    out = c.calibrate(rows, 24, 68)
    assert out['recommendation']['auto_apply'] is False
    assert out['threshold_changed'] is False
    assert out['by_score_band']['60-67']['decisive'] == 40
    assert out['by_score_band']['68-74']['decisive'] == 40


def test_open_rows_do_not_count_as_decisive():
    out = c.calibrate([row(70, None, qualified=True)], 24, 68)
    assert out['overall']['decisive'] == 0
    assert out['matured_observations'] == 0


if __name__ == '__main__':
    test_short_return_is_direction_normalized()
    test_score_bands_respect_threshold()
    test_opportunity_state_separates_watch_armed_actionable()
    test_calibration_never_auto_applies_threshold()
    test_open_rows_do_not_count_as_decisive()
    print('outcome calibration tests: ok')
