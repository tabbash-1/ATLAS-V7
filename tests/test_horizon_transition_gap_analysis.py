#!/usr/bin/env python3
import horizon_transition_gap_analysis as h


def row(r12,r24,hour=10):
    return {
        'return_12h_pct':r12,'return_24h_pct':r24,
        'captured_at':h.base.parse_time(f'2026-08-01T{hour:02d}:00:00+00:00'),
        'symbol':'BTCUSDT','direction':'LONG','corrected_score':70,
        'trend_base':50,'rs_reason':'NEUTRAL','futures_reason':'UNKNOWN',
        'obstacle_reason':'VERY_CLOSE_PRIOR_STRUCTURE','relative_volume_replayed':0.8,
        'direction_votes':3,
    }


def main():
    assert h.transition(row(1,-1)) == 'WIN12_LOSS24'
    assert h.transition(row(1,2)) == 'WIN12_WIN24'
    assert h.transition(row(-1,2)) == 'LOSS12_WIN24'
    assert h.transition(row(-1,-2)) == 'LOSS12_LOSS24'
    assert h.utc_session(row(1,2,13)) == 'UTC_12_17'
    assert h.base.THRESHOLD == 68.0
    print('horizon transition gap analysis tests: ok')

if __name__=='__main__': main()
