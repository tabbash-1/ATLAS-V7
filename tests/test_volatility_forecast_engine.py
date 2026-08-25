import math

import volatility_forecast_engine as vfe


def synthetic_klines(n=240, interval_minutes=60, base=100.0, amp=0.012):
    rows = []
    price = base
    for i in range(n):
        # Deterministic alternating/slow wave: enough movement without randomness.
        move = amp * math.sin(i / 5.0) + (amp * 0.35 if i % 7 == 0 else -amp * 0.08)
        price = max(1.0, price * (1.0 + move))
        high = price * 1.004
        low = price * 0.996
        ts = 1_700_000_000_000 + i * interval_minutes * 60_000
        rows.append([ts, price, high, low, price, 1000])
    return rows


def test_empirical_forecast_is_ready_for_hourly_history():
    out = vfe.analyze('BTCUSDT', synthetic_klines())
    assert out['status'] == 'READY'
    assert out['bar_minutes'] == 60.0
    assert out['probability_calibrated'] is False
    assert out['can_override_production'] is False
    assert out['ready_horizons'] == 3
    for h in ('1', '4', '12'):
        row = out['horizons'][h]
        assert row['status'] == 'READY'
        moves = row['empirical_abs_move_pct']
        assert 0 <= moves['p50'] <= moves['p80'] <= moves['p95']


def test_coarse_bars_do_not_fake_one_hour_forecast():
    out = vfe.analyze('BTCUSDT', synthetic_klines(interval_minutes=240))
    assert out['horizons']['1']['status'] == 'INSUFFICIENT'
    assert out['horizons']['1']['reason'] == 'BAR_INTERVAL_COARSER_THAN_HORIZON'
    assert out['horizons']['4']['status'] == 'READY'


def test_insufficient_history_is_explicit():
    out = vfe.analyze('ETHUSDT', synthetic_klines(n=30))
    assert out['status'] == 'INSUFFICIENT'
    assert out['reason'] == 'INSUFFICIENT_KLINE_HISTORY'
    assert out['can_override_production'] is False


def test_geometry_fit_is_descriptive_not_gate():
    forecast = vfe.analyze('BTCUSDT', synthetic_klines())
    p80 = forecast['horizons']['4']['empirical_abs_move_pct']['p80']
    entry = 100.0
    target = entry * (1 + (p80 * 0.8) / 100.0)
    stop = entry * (1 - (p80 * 0.5) / 100.0)
    fit = vfe.geometry_fit(forecast, 'LONG', entry, stop, target, horizon_h=4)
    assert fit['status'] == 'READY'
    assert fit['target_fit'] == 'PLAUSIBLE_VS_EMPIRICAL_P80'
    assert fit['stop_fit'] == 'PLAUSIBLE_VS_EMPIRICAL_P80'
    assert fit['approval_claimed'] is False
    assert fit['can_override_production'] is False


def test_invalid_directional_geometry_is_rejected_as_insufficient():
    forecast = vfe.analyze('BTCUSDT', synthetic_klines())
    fit = vfe.geometry_fit(forecast, 'SHORT', 100, 98, 105, horizon_h=4)
    assert fit['status'] == 'INSUFFICIENT'
    assert fit['reason'] == 'DIRECTIONALLY_INVALID_GEOMETRY'
