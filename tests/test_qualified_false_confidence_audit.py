#!/usr/bin/env python3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as q


def row(score=70, votes=4, trend=68, volume=2, rs=0, futures=0, obstacle=0):
    return {
        'captured_at': datetime(2026, 8, 24, 12, tzinfo=timezone.utc),
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100.0,
        'stored_score': score, 'corrected_score': score,
        'direction_votes': votes, 'trend_base': trend,
        'volume_bonus': volume, 'stored_volume_bonus': volume,
        'volume_fix_delta': 0.0, 'relative_volume_replayed': 1.2,
        'rs_adjustment': rs, 'futures_adjustment': futures,
        'obstacle_adjustment': obstacle,
    }


def main():
    assert q.bonus_delta(row(), 'FOURTH_VOTE_PREMIUM') == 4.0
    assert q.bonus_delta(row(votes=3, trend=64), 'FOURTH_VOTE_PREMIUM') == 0.0
    assert q.round_score(67.6) == 68
    assert q.round_score(67.4) == 67

    critical = row(score=70, volume=3)
    noncritical = row(score=72, volume=3)
    assert q.round_score(critical['corrected_score'] - q.bonus_delta(critical, 'VOLUME_BONUS')) < q.THRESHOLD
    assert q.round_score(noncritical['corrected_score'] - q.bonus_delta(noncritical, 'VOLUME_BONUS')) >= q.THRESHOLD

    # Guardrails are invariant even when no historical file is involved.
    assert q.THRESHOLD == 68.0
    assert q.SCHEMA == 'ATLAS_V6_QUALIFIED_FALSE_CONFIDENCE_AUDIT_V1'
    print('qualified false confidence audit tests: ok')


if __name__ == '__main__':
    main()
