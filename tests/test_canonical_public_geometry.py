import decision_engine_v7 as engine


def test_public_geometry_mirrors_canonical_trade_plan_and_preserves_qualification_geometry():
    result = {
        'entry': 100.0,
        'stop_loss': 101.0,
        'take_profit': 99.2,
        'risk_reward': 0.8,
        'geometry_gate': {'status': 'PASS', 'qualified': True, 'risk_reward': 1.38},
        'timeframe_matrix': {'swing': {'risk_reward': 1.38}},
    }
    plan = {
        'version': 'PLAN_TEST',
        'status': 'ACTIONABLE',
        'entry': 100.0,
        'stop_loss': 101.0,
        'tp2': 98.0,
        'rr_tp2': 2.0,
    }

    out = engine.sync_public_geometry(result, plan)

    assert out['entry'] == plan['entry']
    assert out['stop_loss'] == plan['stop_loss']
    assert out['take_profit'] == plan['tp2']
    assert out['risk_reward'] == plan['rr_tp2']
    assert out['public_geometry_source'] == 'production_trade_plan'
    assert out['geometry_gate']['risk_reward'] == 2.0
    assert out['geometry_gate']['qualification_risk_reward'] == 1.38
    assert out['qualification_geometry']['take_profit'] == 99.2
    assert out['qualification_geometry']['risk_reward'] == 0.8
    assert out['timeframe_matrix']['swing']['risk_reward'] == 2.0


def test_wait_plan_does_not_rewrite_public_geometry():
    result = {'entry': 100.0, 'take_profit': 99.0, 'risk_reward': 1.0}
    out = engine.sync_public_geometry(result, {'status': 'WAIT'})
    assert out['take_profit'] == 99.0
    assert out['risk_reward'] == 1.0
    assert 'public_geometry_source' not in out
