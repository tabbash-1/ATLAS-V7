from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import swing_episode_calibration as s


def row(t,symbol='BTCUSDT',direction='LONG',obstacle='VERY_CLOSE',ret12=1):
    return {'wait_at':t,'symbol':symbol,'candidate_direction':direction,'score_attribution':{'obstacle_reason':obstacle},'horizons':{'12h':{'directional_return_pct':ret12}}}


def test_repeated_snapshots_inside_12h_are_one_episode():
    rows=[row('2026-08-24T00:00:00+00:00'),row('2026-08-24T01:00:00+00:00'),row('2026-08-24T11:59:00+00:00'),row('2026-08-24T12:00:00+00:00')]
    r=s.build_report({'records':rows})
    assert r['raw_directional_records']==4
    assert r['independent_episode_records']==2
    c=r['combos']['BTCUSDT|LONG|VERY_CLOSE_PRIOR_STRUCTURE']
    assert c['12h']['n']==2
    assert c['verdict']=='INSUFFICIENT_INDEPENDENT_EPISODES'


def test_five_independent_positive_episodes_can_validate_research_edge():
    rows=[row(f'2026-08-{20+i//2:02d}T{(i%2)*12:02d}:00:00+00:00',ret12=1) for i in range(5)]
    r=s.build_report({'records':rows})
    assert r['combos']['BTCUSDT|LONG|VERY_CLOSE_PRIOR_STRUCTURE']['verdict']=='INDEPENDENT_POSITIVE_EDGE'
    assert r['production_threshold_changed'] is False
    assert r['auto_promotion_enabled'] is False


def test_negative_independent_episodes_are_detected_without_promotion():
    rows=[row(f'2026-08-{20+i//2:02d}T{(i%2)*12:02d}:00:00+00:00',symbol='HYPEUSDT',direction='SHORT',ret12=-1) for i in range(5)]
    r=s.build_report({'records':rows})
    c=r['combos']['HYPEUSDT|SHORT|VERY_CLOSE_PRIOR_STRUCTURE']
    assert c['verdict']=='INDEPENDENT_NEGATIVE_EDGE'
    assert c['production_change_allowed'] is False


def test_legacy_and_current_obstacle_labels_are_treated_as_one_series():
    # Pre-refactor rows used the short label; post-refactor rows use the
    # current label for the exact same distance-to-structure bucket. They
    # must accumulate into a single combo, not two fragmented ones.
    legacy_rows=[row(f'2026-08-2{i}T00:00:00+00:00',obstacle='VERY_CLOSE',ret12=1) for i in range(0,3)]
    current_rows=[row(f'2026-08-2{i}T12:00:00+00:00',obstacle='VERY_CLOSE_PRIOR_STRUCTURE',ret12=1) for i in range(0,3)]
    r=s.build_report({'records':legacy_rows+current_rows})
    assert 'BTCUSDT|LONG|VERY_CLOSE' not in r['combos']
    c=r['combos']['BTCUSDT|LONG|VERY_CLOSE_PRIOR_STRUCTURE']
    assert c['raw_episode_candidates']==6
    assert c['verdict']=='INDEPENDENT_POSITIVE_EDGE'


if __name__=='__main__':
    test_repeated_snapshots_inside_12h_are_one_episode()
    test_five_independent_positive_episodes_can_validate_research_edge()
    test_negative_independent_episodes_are_detected_without_promotion()
    test_legacy_and_current_obstacle_labels_are_treated_as_one_series()
    print('swing episode calibration tests: ok')
