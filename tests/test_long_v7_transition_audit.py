#!/usr/bin/env python3
from datetime import datetime, timezone

import long_v7_transition_audit as m


def row(symbol, ts, mom, rsi, ext, rv, trend, px20, atr, ret=0.0):
    return {
        'symbol': symbol,
        'captured_at': ts,
        'momentum_24h_pct': mom,
        'rsi14': rsi,
        'price_extension_atr': ext,
        'paced_relative_volume': rv,
        'ema20_vs_ema50_pct': trend,
        'price_vs_ema20_pct': px20,
        'atr_pct': atr,
        'return_12h_pct': ret,
    }


def test_backward_only_transition_windows():
    rows = [
        row('BTCUSDT', '2026-08-20T00:00:00+00:00', 1, 50, 0.2, 1.0, 0.1, 0.2, 1.0),
        row('BTCUSDT', '2026-08-20T01:00:00+00:00', 2, 52, 0.4, 1.2, 0.2, 0.4, 1.1),
        row('BTCUSDT', '2026-08-20T03:00:00+00:00', 4, 58, 0.8, 1.8, 0.4, 0.8, 1.3),
    ]
    out = m.add_transitions(rows)
    last = out[-1]
    assert '3h' in last['transition_complete_lags']
    assert last['delta_momentum_24h_pct_3h'] == 3
    assert last['delta_rsi14_3h'] == 8
    # 1h prior is absent at 03:00 because the nearest prior is 2h old.
    assert '1h' not in last['transition_complete_lags']


def test_nearest_prior_never_uses_future():
    hist = [
        row('X', '2026-08-20T01:00:00+00:00', 1, 50, 0, 1, 0, 0, 1),
        row('X', '2026-08-20T03:00:00+00:00', 9, 90, 9, 9, 9, 9, 9),
    ]
    now = datetime(2026, 8, 20, 2, 0, tzinfo=timezone.utc)
    prior, age = m.nearest_prior(hist, now, 0.5, 1.5)
    assert prior['captured_at'].startswith('2026-08-20T01:00')
    assert age == 1.0


def test_guardrails():
    src = open(m.__file__, encoding='utf-8').read()
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'live_execution': False" in src
    assert "'future_feature_leakage_allowed': False" in src


if __name__ == '__main__':
    test_backward_only_transition_windows()
    test_nearest_prior_never_uses_future()
    test_guardrails()
    print('long v7 transition audit tests: ok')
