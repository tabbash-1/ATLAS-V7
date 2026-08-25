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
    payload={'records':[
        row('2026-08-25T10:00:00+00:00'),
        row('2026-08-25T11:00:00+00:00'),
    ]}
    r=v.build_report(payload)
    assert r['eligible_records_after_cutoff']==1
    assert r['tiers']['HIGH']['horizons']['12h']['n']==1
    assert r['production_threshold_changed'] is False
    assert r['production_score_adjustment']==0
    assert r['auto_promotion_enabled'] is False


def test_high_and_low_tiers_are_separated():
    payload={'records':[
        row('2026-08-25T11:00:00+00:00',symbol='BTCUSDT',direction='LONG',ret12=1.2),
        row('2026-08-25T11:01:00+00:00',symbol='HYPEUSDT',direction='SHORT',ret12=-1.1),
        row('2026-08-25T11:02:00+00:00',symbol='XRPUSDT',direction='LONG',obstacle='VERY_CLOSE_PRIOR_STRUCTURE',ret12=.2),
    ]}
    r=v.build_report(payload,target=2)
    assert r['tiers']['HIGH']['horizons']['12h']['mean_pct']==1.2
    assert r['tiers']['LOW']['horizons']['12h']['mean_pct']==-1.1
    assert r['tiers']['NEUTRAL']['horizons']['12h']['n']==1
    assert r['promotion_gate']['status']=='COLLECTING'


def test_gate_never_auto_promotes_even_when_research_validates():
    rows=[row(f'2026-08-25T11:{i:02d}:00+00:00',ret12=1.0) for i in range(3)]
    r=v.build_report({'records':rows},target=3)
    assert r['promotion_gate']['status']=='RESEARCH_VALIDATED_REVIEW_ONLY'
    assert r['promotion_gate']['production_change_allowed'] is False
    assert r['auto_promotion_enabled'] is False
    assert r['production_threshold']==68


def test_scores_outside_60_67_do_not_enter_forward_validation():
    payload={'records':[
        row('2026-08-25T11:00:00+00:00',score=59),
        row('2026-08-25T11:01:00+00:00',score=68),
        row('2026-08-25T11:02:00+00:00',score=67),
    ]}
    r=v.build_report(payload)
    assert r['eligible_records_after_cutoff']==1


if __name__=='__main__':
    test_pre_cutoff_rows_are_excluded()
    test_high_and_low_tiers_are_separated()
    test_gate_never_auto_promotes_even_when_research_validates()
    test_scores_outside_60_67_do_not_enter_forward_validation()
    print('swing quality forward validation tests: ok')
