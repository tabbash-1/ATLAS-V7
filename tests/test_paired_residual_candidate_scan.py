#!/usr/bin/env python3
import paired_residual_candidate_scan as s


def main():
    assert s.base.THRESHOLD == 68.0
    row = {
        'direction':'LONG',
        'obstacle_reason':'VERY_CLOSE_PRIOR_STRUCTURE',
        'rs_reason':'NEUTRAL',
        'relative_volume_replayed':0.9,
        'corrected_score':72,
        'direction_votes':3,
        'trend_base':60,
    }
    assert s.bucket_match(row,'relative_strength','NEUTRAL') is True
    assert s.bucket_match(row,'direction_x_rs','LONG|NEUTRAL') is True
    print('paired residual candidate scan tests: ok')

if __name__=='__main__':
    main()
