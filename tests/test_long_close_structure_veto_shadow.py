#!/usr/bin/env python3
import long_close_structure_veto_shadow as s


def row(direction='LONG', obstacle='CLOSE_PRIOR_STRUCTURE', score=72, votes=3, trend=64):
    return {
        'direction': direction, 'obstacle_reason': obstacle,
        'corrected_score': score, 'direction_votes': votes, 'trend_base': trend,
    }


def main():
    assert s.is_vetoed(row()) is True
    assert s.is_vetoed(row(direction='SHORT')) is False
    assert s.is_vetoed(row(obstacle='VERY_CLOSE_PRIOR_STRUCTURE')) is False
    assert s.baseline_qualified(row()) is True
    assert s.candidate_qualified(row()) is False
    assert s.base.THRESHOLD == 68.0
    print('long close structure veto shadow tests: ok')


if __name__ == '__main__':
    main()
