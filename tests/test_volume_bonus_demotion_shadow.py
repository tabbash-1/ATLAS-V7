#!/usr/bin/env python3
from datetime import datetime, timezone
import volume_bonus_demotion_shadow as s


def row(score, volume):
    return {
        'captured_at': datetime(2026, 8, 24, 12, tzinfo=timezone.utc),
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100.0,
        'corrected_score': score, 'volume_bonus': volume,
    }


def main():
    assert s.candidate_score(row(70, 3)) == 67
    assert s.candidate_score(row(72, 3)) == 69
    assert s.base.THRESHOLD == 68.0
    assert s.SCHEMA == 'ATLAS_V6_VOLUME_BONUS_DEMOTION_SHADOW_V1'
    print('volume bonus demotion shadow tests: ok')


if __name__ == '__main__':
    main()
