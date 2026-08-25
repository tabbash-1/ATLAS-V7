from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import swing_quality_forward_validation as v


def row(wait_at, symbol='BTCUSDT', direction='LONG', obstacle='VERY_CLOSE', score=65, ret12=1.0, ret24=1.5):
    return {
        'wait_at':wait_at,'symbol':symbol,'candidate_direction':direction,'score':score,
        'score_attribution':{'obstacle_reason':obstacle},
        'horizons':{'12h':{'directional_return_pct':ret12},'24h':{'directional_return_pct':ret24}},
    }


def test_pre_cutoff_rows_are_excluded():
    payload={'records':[row('2026-08-25T10:00:00+00:00'),row('2026-08-25T11:00:00+00:00')]}
    r=v.build_report(payload)
    assert r['raw_eligible_records_after_cutoff']==1
    assert r['independent_episodes_after_cutoff']==1
    assert r['tiers']['PROVISIONAL_POSITIVE']['horizons']['12h']['n']==1
    assert r['production_threshold_changed'] is False
    assert r['production_score_adjustment']==0
    assert r['auto_promotion_enabled'] is False


def test_repeated_same_combo_inside_12h_is_one_forward_episode():
    payload={'records':[
        row('2026-08-25T11:00:00+00:00'),
        row('2026-08-25T12:00:00+00:00'),
        row('2026-08-25T22:59:00+00:00'),
        row('2026-08-25T23:00:00+00:00'),
    ]}
    r=v.build_report(payload)
    assert r['raw_eligible_records_after_cutoff']==4
    assert r['independent_episodes_after_cutoff']==2
    assert r['tiers']['PROVISIONAL_POSITIVE']['horizons']['12h']['n']==2


def test_positive_negative_and_neutral_tiers_are_separated():
    payload={'records':[
        row('2026-08-25T11:00:00+00:00',symbol='BTCUSDT',direction='LONG',ret12=1.2),
        row('2026-08-25T11:01:00+00:00',symbol='HYPEUSDT',direction='SHORT',ret12=-1.1),
        row('2026-08-25T11:02:00+00:00',symbol='XRPUSDT',direction='LONG',obstacle='VERY_CLOSE_PRIOR_STRUCTURE',ret12=.2),
    ]}
    r=v.build_report(payload,preliminary_target=2,strong_target=4)
    assert r['tiers']['PROVISIONAL_POSITIVE']['horizons']['12h']['mean_pct']==1.2
    assert r['tiers']['PROVISIONAL_NEGATIVE']['horizons']['12h']['mean_pct']==-1.1
    assert r['tiers']['NEUTRAL']['horizons']['12h']['n']==1
    assert r['promotion_gate']['status']=='COLLECTING_INDEPENDENT_EPISODES'


def test_gate_never_auto_promotes_even_when_preliminary_validates():
    rows=[
        row('2026-08-25T11:00:00+00:00',symbol='BTCUSDT',ret12=1.0),
        row('2026-08-25T11:01:00+00:00',symbol='ETHUSDT',ret12=1.0),
        row('2026-08-25T11:02:00+00:00',symbol='BNBUSDT',ret12=1.0),
    ]
    r=v.build_report({'records':rows},preliminary_target=3,strong_target=6)
    assert r['promotion_gate']['status']=='PRELIMINARY_VALIDATED_REVIEW_ONLY'
    assert r['promotion_gate']['production_change_allowed'] is False
    assert r['auto_promotion_enabled'] is False
    assert r['production_threshold']==68


def test_scores_outside_60_67_do_not_enter_forward_validation():
    payload={'records':[row('2026-08-25T11:00:00+00:00',score=59),row('2026-08-25T11:01:00+00:00',score=68),row('2026-08-25T11:02:00+00:00',score=67)]}
    r=v.build_report(payload)
    assert r['raw_eligible_records_after_cutoff']==1


if __name__=='__main__':
    test_pre_cutoff_rows_are_excluded()
    test_repeated_same_combo_inside_12h_is_one_forward_episode()
    test_positive_negative_and_neutral_tiers_are_separated()
    test_gate_never_auto_promotes_even_when_preliminary_validates()
    test_scores_outside_60_67_do_not_enter_forward_validation()
    print('swing quality forward validation tests: ok')
