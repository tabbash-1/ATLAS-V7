import wait_diagnostics as w


def rec(direction='LONG', score=65, ret=2.0, raw=2.0, reason='SCORE_BELOW_SIGNAL_THRESHOLD', obstacle=0):
    return {
        'symbol':'BTCUSDT','candidate_direction':direction,'score':score,'threshold':68,
        'reason':reason,'score_attribution':{'obstacle_adjustment':obstacle},
        'horizons':{'24h':{'directional_return_pct':ret,'change_pct':raw}}
    }


def test_directional_gain_is_missed_opportunity():
    assert w.classify(rec(ret=1.5),24) == 'MISSED_DIRECTIONAL_OPPORTUNITY'


def test_directional_loss_is_correct_wait_protection():
    assert w.classify(rec(ret=-1.5, raw=-1.5),24) == 'WAIT_PROTECTED_CAPITAL'


def test_no_consensus_big_move_is_not_called_missed_signal():
    r=rec(direction='NONE',score=None,ret=None,raw=4.0,reason='NO_DIRECTIONAL_CONSENSUS')
    assert w.classify(r,24) == 'MATERIAL_MOVE_WITHOUT_CONSENSUS'


def test_obstacle_penalty_is_attributed():
    assert w.blocker(rec(obstacle=-8)) == 'STRUCTURE_OBSTACLE_PENALTY'


def test_diagnostics_never_change_threshold_or_execution():
    out=w.diagnose({'records':[rec(),rec(ret=-2,raw=-2)]},24)
    assert out['safety']['threshold_changed'] is False
    assert out['safety']['execution_rules_changed'] is False
    assert out['overall']['directional_decisive'] == 2


if __name__ == '__main__':
    test_directional_gain_is_missed_opportunity()
    test_directional_loss_is_correct_wait_protection()
    test_no_consensus_big_move_is_not_called_missed_signal()
    test_obstacle_penalty_is_attributed()
    test_diagnostics_never_change_threshold_or_execution()
    print('wait diagnostics tests: ok')
