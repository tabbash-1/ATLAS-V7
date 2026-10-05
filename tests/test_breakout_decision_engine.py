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


def test_initial_breakout_event_is_not_entry_ready_until_post_break_hold():
    rows=base_series()
    prior_high=max(x['high'] for x in rows[-26:-2])
    px=prior_high+1.0
    rows[-2]=candle(98,px,high=px+0.2,low=px-0.7,open_=px-0.8,volume=150)
    rows[-1]=candle(99,px+0.05,high=px+0.1,low=px-0.05,open_=px)
    ctx=scoring.breakout_context(rows,px+0.05,'LONG',4,2.0,1.0,1.0,closed_rv=1.5)
    assert ctx['breakout_event_confirmed'] is True
    assert ctx['confirmed'] is False
    assert ctx['entry_ready'] is False
    assert ctx['acceptance_mode']=='NONE'


def test_accepted_breakout_retest_clears_false_obstacle_penalty():
    rows=base_series()
    level=max(x['high'] for x in rows[-27:-3])
    breakout_close=level+1.0
    rows[-3]=candle(97,breakout_close,high=breakout_close+0.2,low=level+0.2,open_=level+0.1,volume=160)
    rows[-2]=candle(98,level+0.55,high=level+0.8,low=level-0.05,open_=level+0.35,volume=110)
    rows[-1]=candle(99,level+0.60,high=level+0.75,low=level+0.4,open_=level+0.55)
    ctx=scoring.breakout_context(rows,level+0.60,'LONG',4,2.0,1.0,1.0,closed_rv=1.1)
    assert ctx['confirmed'] is True
    assert ctx['entry_ready'] is True
    assert ctx['accepted'] is True
    assert ctx['acceptance_mode']=='RETEST_HOLD'
    assert ctx['acceptance_level'] is not None
    assert ctx['breakout_age_bars']==1
    adj,reason=scoring.obstacle_adjustment(None,'NO_PRIOR_RESISTANCE_AHEAD',ctx['confirmed'])
    assert adj==3
    assert reason=='CONFIRMED_BREAKOUT_CLEAR_SPACE'


def test_breakout_that_closes_back_inside_structure_is_not_accepted():
    rows=base_series()
    level=max(x['high'] for x in rows[-27:-3])
    breakout_close=level+0.8
    rows[-3]=candle(97,breakout_close,high=breakout_close+0.2,low=level+0.1,open_=level,volume=160)
    rows[-2]=candle(98,level-0.2,high=level+0.2,low=level-0.4,open_=level+0.1,volume=120)
    rows[-1]=candle(99,level-0.1,high=level+0.1,low=level-0.3,open_=level-0.2)
    ctx=scoring.breakout_context(rows,level-0.1,'LONG',4,1.0,1.0,0.9,closed_rv=1.2)
    assert ctx['accepted'] is False
    assert ctx['confirmed'] is False


def test_historical_breakout_cannot_be_retroactively_upgraded_by_current_votes():
    rows=[]
    # Persistent downtrend: a single range break can close above the recent
    # 24H high, but the breakout bar itself still lacks 4/4 trend votes.
    for i in range(100):
        px=200-i*0.5
        rows.append(candle(i,px,high=px+0.2,low=px-0.2,open_=px+0.1,volume=100))
    level=max(x['high'] for x in rows[-27:-3])
    event_close=level+0.6
    rows[-3]=candle(97,event_close,high=event_close+0.2,low=level+0.1,open_=level-0.1,volume=180)
    rows[-2]=candle(98,event_close+0.2,high=event_close+0.35,low=level+0.05,open_=event_close+0.05,volume=120)
    rows[-1]=candle(99,event_close+0.25,high=event_close+0.4,low=event_close+0.1,open_=event_close+0.15,volume=110)

    event_ctx=scoring._event_direction_context(rows[:-1],len(rows[:-1])-2,'LONG')
    assert event_ctx['votes'] < 4

    # Simulate a caller whose CURRENT state later reports perfect votes/momentum.
    ctx=scoring.breakout_context(rows,event_close+0.25,'LONG',4,5.0,1.0,1.0,closed_rv=1.1)
    assert ctx['accepted'] is False
    assert ctx['entry_ready'] is False
    assert ctx['event_time_directional_evidence_required'] is True


def test_accepted_breakout_freezes_event_time_evidence():
    rows=base_series()
    level=max(x['high'] for x in rows[-27:-3])
    breakout_close=level+1.0
    rows[-3]=candle(97,breakout_close,high=breakout_close+0.2,low=level+0.2,open_=level+0.1,volume=160)
    rows[-2]=candle(98,level+0.55,high=level+0.8,low=level-0.05,open_=level+0.35,volume=110)
    rows[-1]=candle(99,level+0.60,high=level+0.75,low=level+0.4,open_=level+0.55)
    ctx=scoring.breakout_context(rows,level+0.60,'LONG',4,2.0,1.0,1.0,closed_rv=1.1)
    assert ctx['accepted'] is True
    assert ctx['accepted_breakout_event_votes'] == 4
    assert ctx['accepted_breakout_event_momentum_24h_pct'] is not None
    assert ctx['accepted_breakout_event_rsi14'] is not None
    assert ctx['current_directional_evidence_required'] is True


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
    assert abs(paced - 1.0) < 1e-12
    assert abs(scoring.paced_relative_volume(0.02, 0.10) - 0.2) < 1e-12


if __name__ == '__main__':
    test_current_candle_high_is_not_resistance()
    test_initial_breakout_event_is_not_entry_ready_until_post_break_hold()
    test_accepted_breakout_retest_clears_false_obstacle_penalty()
    test_breakout_that_closes_back_inside_structure_is_not_accepted()
    test_historical_breakout_cannot_be_retroactively_upgraded_by_current_votes()
    test_accepted_breakout_freezes_event_time_evidence()
    test_false_breakout_without_confirmation_gets_no_bonus()
    test_partial_hour_volume_is_paced_not_compared_as_full_hour()
    print('breakout decision engine tests: ok')
