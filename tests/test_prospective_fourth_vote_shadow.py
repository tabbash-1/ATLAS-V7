#!/usr/bin/env python3
import prospective_fourth_vote_shadow as s


def main():
    row={
        'symbol':'BTCUSDT','direction':'LONG','final_score':70,
        'production_signal_qualified':True,'direction_votes':4,
        'score_attribution':{'trend_base':68},
    }
    r=s.shadow_from_row(row,68)
    assert r['production_score']==70.0
    assert r['fourth_vote_premium_removed']==4.0
    assert r['shadow_score']==66
    assert r['production_qualified'] is True
    assert r['shadow_qualified'] is False
    assert r['qualification_changed'] is True
    assert r['can_override_production'] is False
    assert r['production_threshold_changed'] is False
    assert r['live_execution'] is False

    r2=s.shadow_from_row({**row,'direction_votes':3,'score_attribution':{'trend_base':64}},68)
    assert r2['fourth_vote_premium_removed']==0.0
    assert r2['shadow_score']==70
    print('prospective fourth vote shadow tests: ok')

if __name__=='__main__':
    main()
