#!/usr/bin/env python3
from datetime import datetime, timezone

import long_v7_transition_representation_audit as m


def dt(h, minute=0):
    return datetime(2026, 8, 20, h, minute, tzinfo=timezone.utc)


def state(ts, ema20=100.0, rsi=60.0, mom=1.0, spread=0.5, atrp=1.0, rv=1.0):
    return {
        'ts': ts,
        'ema20': ema20,
        'rsi14': rsi,
        'momentum_24h_pct': mom,
        'ema_spread_pct': spread,
        'atr_over_ema20_pct': atrp,
        'paced_relative_volume': rv,
    }


def test_nearest_prior_is_strict_and_respects_window():
    rows = [state(dt(8)), state(dt(9)), state(dt(10))]
    times = [x['ts'] for x in rows]
    x = m.nearest_prior(rows, times, dt(11), 60, 35)
    assert x['ts'] == dt(10)
    assert x['ts'] < dt(11)
    y = m.nearest_prior(rows, times, dt(11), 180, 35)
    assert y['ts'] == dt(8)


def test_transition_features_direction():
    cur = state(dt(11), ema20=102, rsi=64, mom=2.5, spread=1.2, atrp=1.3, rv=1.8)
    old = state(dt(10), ema20=100, rsi=60, mom=1.0, spread=0.5, atrp=1.0, rv=1.1)
    out = m.transition_features(cur, old, '1h')
    assert out['delta_rsi14_1h'] == 4
    assert out['delta_momentum_24h_pct_1h'] == 1.5
    assert out['delta_ema_spread_pct_1h'] == 0.7
    assert round(out['ema20_change_pct_1h'], 6) == 2.0


def test_guardrails():
    src = open(m.__file__, encoding='utf-8').read()
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src
    assert 'strictly before the decision time' in src


if __name__ == '__main__':
    test_nearest_prior_is_strict_and_respects_window()
    test_transition_features_direction()
    test_guardrails()
    print('long v7 transition representation audit tests: ok')
