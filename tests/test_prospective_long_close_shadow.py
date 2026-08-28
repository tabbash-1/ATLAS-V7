#!/usr/bin/env python3
import prospective_long_close_shadow as s


def main():
    row={
        'symbol':'BTCUSDT','direction':'LONG','final_score':72,
        'production_signal_qualified':True,'direction_votes':3,
        'score_attribution':{'trend_base':64,'obstacle_reason':'CLOSE_PRIOR_STRUCTURE'},
    }
    r=s.combined_shadow_from_row(row,68)
    assert r['production_qualified'] is True
    assert r['fourth_vote_shadow_qualified'] is True
    assert r['long_close_structure_veto'] is True
    assert r['combined_shadow_qualified'] is False
    assert r['can_override_production'] is False
    assert r['production_threshold_changed'] is False
    assert r['live_execution'] is False

    r2=s.combined_shadow_from_row({**row,'direction':'SHORT'},68)
    assert r2['long_close_structure_veto'] is False
    assert r2['combined_shadow_qualified'] is True
    print('prospective long close shadow tests: ok')

if __name__=='__main__':
    main()
