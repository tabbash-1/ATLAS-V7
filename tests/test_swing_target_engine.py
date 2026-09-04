import swing_target_engine as s


def test_swing_ready_requires_large_enough_move_and_rr():
    x = s.build(
        direction='LONG', entry=100.0, stop=98.0, atr=2.0,
        structural_geometry={'obstacle_price':106.0, 'breakout':{'prior_24h_high':108.0}},
        continuation_strong=True, breakout_confirmed=True,
    )
    assert x['status'] == 'SWING_READY'
    assert x['tp1'] > 100.0
    assert x['tp2'] >= 108.0
    assert x['tp3_runner'] > x['tp2']
    assert x['rr_tp2'] >= 2.5
    assert x['projected_tp2_move_pct'] >= 1.5


def test_small_market_room_is_quick_only():
    x = s.build(
        direction='LONG', entry=100.0, stop=99.5, atr=0.2,
        structural_geometry={'obstacle_price':100.6, 'breakout':{'prior_24h_high':100.8}},
        continuation_strong=False, breakout_confirmed=False,
    )
    assert x['status'] == 'QUICK_ONLY'
    assert x['projected_tp2_move_pct'] < 1.5


def test_short_swing_ordering():
    x = s.build(
        direction='SHORT', entry=100.0, stop=102.0, atr=2.0,
        structural_geometry={'obstacle_price':94.0, 'breakout':{'prior_24h_low':92.0}},
        continuation_strong=True, breakout_confirmed=False,
    )
    assert x['status'] == 'SWING_READY'
    assert x['stop_loss'] > x['entry'] > x['tp1'] > x['tp2'] > x['tp3_runner']


def test_production_plan_keeps_extended_swing_context_but_core_is_4_12h():
    import production_trade_plan as p
    d = {
        'ok': True, 'candidate_direction': 'LONG', 'entry': 100.0,
        'indicators': {'atr14': 2.0}, 'production_signal_qualified': True,
        'execution_ready': True,
        'structural_geometry': {
            'obstacle_price': 106.0, 'continuation_strong': True,
            'breakout': {'confirmed': True, 'prior_24h_high': 108.0}
        }
    }
    x = p.build(d)
    assert x['core_plan']['tp1'] == x['tp1']
    assert x['core_plan']['tp2'] == x['tp2']
    assert x['core_plan']['horizon'] == '4-12H'
    assert x['preferred_target_lane'] == 'CORE_4_12H'
    assert x['swing_plan']['status'] == 'SWING_READY'
    assert x['swing_plan']['role'] == 'CONTEXT_ONLY'
    assert x['swing_plan']['can_override_core'] is False
    assert x['swing_plan']['tp3_runner'] > x['swing_plan']['tp2']
