#!/usr/bin/env python3
from datetime import datetime, timezone, timedelta

from long_v7_fixed_episode_split import full_fixed_episodes, split_fixed_60_40


def row(symbol, hour, ret=1.0):
    return {
        'symbol': symbol,
        'direction': 'LONG',
        'captured_at': datetime(2026, 8, 20, tzinfo=timezone.utc) + timedelta(hours=hour),
        'return_12h_pct': ret,
    }


def test_decorrelate_before_split_prevents_boundary_double_anchor():
    # Same-symbol rows at h=0 and h=10 belong to one 12h episode; h=14 is still
    # inside the first 12h anchor window, while h=13+ from a new accepted anchor
    # depends on the independent selector. The core invariant is that splitting
    # fixed episodes can never create extra episodes.
    rows = [
        row('BTCUSDT', 0),
        row('BTCUSDT', 10),
        row('BTCUSDT', 13),
        row('ETHUSDT', 1),
        row('ETHUSDT', 14),
        row('SOLUSDT', 2),
        row('SOLUSDT', 15),
    ]
    full = full_fixed_episodes(rows)
    train, holdout, _ = split_fixed_60_40(full)
    assert len(train) + len(holdout) == len(full)
    tk = {(r['symbol'], str(r['captured_at'])) for r in train}
    hk = {(r['symbol'], str(r['captured_at'])) for r in holdout}
    assert not (tk & hk)


def test_single_episode_split_is_safe():
    full = full_fixed_episodes([row('BTCUSDT', 0)])
    train, holdout, _ = split_fixed_60_40(full)
    assert len(full) == 1
    assert len(train) == 1
    assert len(holdout) == 0


if __name__ == '__main__':
    test_decorrelate_before_split_prevents_boundary_double_anchor()
    test_single_episode_split_is_safe()
    print('long v7 fixed episode split tests: ok')
