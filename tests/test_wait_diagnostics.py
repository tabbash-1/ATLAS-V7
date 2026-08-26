import wait_diagnostics as w


def rec(direction='LONG', score=65, ret=2.0, raw=2.0, reason='SCORE_BELOW_SIGNAL_THRESHOLD', obstacle=0, symbol='BTCUSDT'):
    return {
        'symbol':symbol,'candidate_direction':direction,'score':score,'threshold':68,
        'reason':reason,'score_attribution':{'obstacle_adjustment':obstacle},
        'horizons':{
            '1h':{'directional_return_pct':ret,'change_pct':raw},
            '3h':{'directional_return_pct':ret,'change_pct':raw},
            '6h':{'directional_return_pct':ret,'change_pct':raw},
            '12h':{'directional_return_pct':ret,'change_pct':raw},
            '24h':{'directional_return_pct':ret,'change_pct':raw},
        }
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


def test_structure_segment_tracks_severity_and_score_gap():
    assert w.blocker_segment(rec(score=67, obstacle=-8)) == 'STRUCTURE_OBSTACLE_PENALTY|PENALTY_8_PLUS|GAP_0_1'
    assert w.blocker_segment(rec(score=65, obstacle=-4)) == 'STRUCTURE_OBSTACLE_PENALTY|PENALTY_4_7|GAP_2_3'


def test_diagnostics_never_change_threshold_or_execution():
    out=w.diagnose({'records':[rec(),rec(ret=-2,raw=-2)]},24)
    assert out['safety']['threshold_changed'] is False
    assert out['safety']['execution_rules_changed'] is False
    assert out['safety']['production_weights_changed'] is False
    assert out['overall']['directional_decisive'] == 2
    assert 'by_blocker_segment' in out


def test_small_sample_cannot_propose_shadow_adjustment():
    rows=[rec(obstacle=-8,ret=2.0) for _ in range(10)]
    c=w.calibration({'records':rows})
    p=next(x for x in c['proposals'] if x['blocker']=='STRUCTURE_OBSTACLE_PENALTY')
    assert p['eligible_for_shadow_experiment'] is False
    assert p['suggested_shadow_adjustment_points'] == 0
    assert c['production_change_authorized'] is False


def test_repeated_multi_horizon_misses_can_only_propose_shadow_adjustment():
    rows=[rec(obstacle=-8,ret=2.0) for _ in range(20)]
    c=w.calibration({'records':rows})
    p=next(x for x in c['proposals'] if x['blocker']=='STRUCTURE_OBSTACLE_PENALTY')
    assert p['eligible_for_shadow_experiment'] is True
    assert len(p['confirming_horizons_h']) >= 2
    assert 0 < p['suggested_shadow_adjustment_points'] <= 2
    assert p['production_applied'] is False
    assert c['threshold_changed'] is False
    assert c['execution_rules_changed'] is False


def test_protective_broad_blocker_can_contain_eligible_narrow_segment():
    rows=[]
    rows += [rec(score=67,obstacle=-8,ret=2.0) for _ in range(20)]
    rows += [rec(score=55,obstacle=-8,ret=-2.0,raw=-2.0) for _ in range(40)]
    c=w.calibration({'records':rows})
    broad=next(x for x in c['proposals'] if x['blocker']=='STRUCTURE_OBSTACLE_PENALTY')
    narrow=next(x for x in c['segment_proposals'] if x['segment']=='STRUCTURE_OBSTACLE_PENALTY|PENALTY_8_PLUS|GAP_0_1')
    assert broad['eligible_for_shadow_experiment'] is False
    assert narrow['eligible_for_shadow_experiment'] is True
    assert narrow['production_applied'] is False
    assert c['eligible_segment_count'] >= 1


def test_no_directional_consensus_is_never_auto_relaxed():
    rows=[rec(direction='NONE',score=None,ret=None,raw=3.0,reason='NO_DIRECTIONAL_CONSENSUS') for _ in range(30)]
    c=w.calibration({'records':rows})
    p=next(x for x in c['proposals'] if x['blocker']=='NO_DIRECTIONAL_CONSENSUS')
    assert p['eligible_for_shadow_experiment'] is False
    assert p['suggested_shadow_adjustment_points'] == 0


if __name__ == '__main__':
    test_directional_gain_is_missed_opportunity()
    test_directional_loss_is_correct_wait_protection()
    test_no_consensus_big_move_is_not_called_missed_signal()
    test_obstacle_penalty_is_attributed()
    test_structure_segment_tracks_severity_and_score_gap()
    test_diagnostics_never_change_threshold_or_execution()
    test_small_sample_cannot_propose_shadow_adjustment()
    test_repeated_multi_horizon_misses_can_only_propose_shadow_adjustment()
    test_protective_broad_blocker_can_contain_eligible_narrow_segment()
    test_no_directional_consensus_is_never_auto_relaxed()
    print('wait diagnostics tests: ok')
