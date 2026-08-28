#!/usr/bin/env python3
from datetime import datetime, timezone
import fourth_vote_demotion_shadow as s


def row(score=70, votes=4, trend=68):
    return {'captured_at': datetime(2026,8,24,12,tzinfo=timezone.utc), 'symbol':'BTCUSDT', 'direction':'LONG', 'entry':100.0, 'corrected_score':score, 'direction_votes':votes, 'trend_base':trend}


def main():
    assert s.premium(row()) == 4.0
    assert s.premium(row(votes=3, trend=64)) == 0.0
    assert s.candidate_score(row(score=70)) == 66
    assert s.base.THRESHOLD == 68.0
    print('fourth vote demotion shadow tests: ok')

if __name__ == '__main__':
    main()
