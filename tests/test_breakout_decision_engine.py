import production_signal_scoring as scoring


def candle(i, close, high=None, low=None, open_=None, volume=100, open_time=None):
    return {
        'open_time': i * 3600000 if open_time is None else open_time,
        'open': close if open_ is None else open_,
        'high': close if high is None else high,
        'low': close if low is None else low,
        'close': close,
        'volume': volume,
    }


def base_series():
    rows=[]
    for i in range(100):
        px=100 + i * 0.05
        rows.append(candle(i, px, high=px+0.2, low=px-0.2))
    return rows


def test_current_candle_high_is_not_resistance():
    rows=base_series()
    px=rows[-2]['high'] + 1.0
    rows[-1]=candle(100, px, high=px+0.01, low=px-0.5, open_=px-0.6)
    level, distance, source=scoring.structural_obstacle(rows, px, 'LONG')
    assert level is None or level > px * 1.0015
    assert source != 'CURRENT_CANDLE_HIGH'


def test_confirmed_breakout_clears_false_obstacle_penalty():
    rows=base_series()
    prior_high=max(x['high'] for x in rows[-25:-1])
    px=prior_high + 1.0
    rows[-1]=candle(100, px, high=px+0.2, low=px-0.7, open_=px-0.8)
    ctx=scoring.breakout_context(rows, px, 'LONG', 4, 2.0, 1.0, 1.0)
    assert ctx['confirmed'] is True
    adj, reason=scoring.obstacle_adjustment(None, 'NO_PRIOR_RESISTANCE_AHEAD', True)
    assert adj == 3
    assert reason == 'CONFIRMED_BREAKOUT_CLEAR_SPACE'


def test_false_breakout_without_confirmation_gets_no_bonus():
    rows=base_series()
    prior_high=max(x['high'] for x in rows[-25:-1])
    px=prior_high + 0.1
    rows[-1]=candle(100, px, high=px+0.05, low=px-0.05, open_=px-0.02)
    ctx=scoring.breakout_context(rows, px, 'LONG', 3, 0.1, 1.0, 0.2)
    assert ctx['confirmed'] is False
    adj, _=scoring.obstacle_adjustment(None, 'NO_PRIOR_RESISTANCE_AHEAD', False)
    assert adj == 0


def test_partial_hour_volume_is_paced_not_compared_as_full_hour():
    raw=0.10
    paced=scoring.paced_relative_volume(raw, 0.10)
    assert paced == 1.0
    assert scoring.paced_relative_volume(0.02, 0.10) == 0.2


if __name__ == '__main__':
    test_current_candle_high_is_not_resistance()
    test_confirmed_breakout_clears_false_obstacle_penalty()
    test_false_breakout_without_confirmation_gets_no_bonus()
    test_partial_hour_volume_is_paced_not_compared_as_full_hour()
    print('breakout decision engine tests: ok')
