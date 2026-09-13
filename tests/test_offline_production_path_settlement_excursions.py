import offline_production_path_settlement as ops


def geom(direction='LONG'):
    if direction == 'LONG':
        return {
            'direction': 'LONG', 'entry': 100.0, 'stop_loss': 99.0,
            'tp1': 101.0, 'tp2': 102.0, 'rr_tp1': 1.0,
            'rr_tp2': 2.0, 'risk_abs': 1.0,
        }
    return {
        'direction': 'SHORT', 'entry': 100.0, 'stop_loss': 101.0,
        'tp1': 99.0, 'tp2': 98.0, 'rr_tp1': 1.0,
        'rr_tp2': 2.0, 'risk_abs': 1.0,
    }


def candle(ts, low, high, close=100.0):
    return {'open_time': ts, 'open': 100.0, 'high': high, 'low': low, 'close': close}


def episode(direction='LONG'):
    return {
        'id': 'research-1', 'symbol': 'BTCUSDT', 'captured_at_ms': 0,
        'captured_at': '1970-01-01T00:00:00+00:00', 'score': 80.0,
        'threshold': 68.0, 'playbook': None, 'regime': None,
        'execution_ready_at_capture': True, 'geometry': geom(direction),
    }


def test_tp2_winner_ignores_post_exit_adverse_spike():
    old_market = ops.market_klines
    try:
        rows = [
            candle(0, 99.5, 100.5),
            candle(300_000, 100.5, 102.2),
            candle(600_000, 94.0, 102.0),  # huge adverse move after TP2 exit
        ]
        ops.market_klines = lambda *args: (rows, 'TEST')
        out = ops.settle(episode('LONG'), ops.HORIZON_H * 3600_000)
        assert out['status'] == 'WIN_TP2'
        assert out['r_multiple'] == 2.0
        assert out['excursion_scope'] == 'THROUGH_TERMINAL_EVENT'
        assert out['mae_r'] == 0.5
        assert out['mfe_r'] == 2.2
    finally:
        ops.market_klines = old_market


def test_ambiguous_5m_uses_only_1m_bars_through_resolved_exit():
    old_market = ops.market_klines
    try:
        five = [
            candle(0, 99.5, 100.5),
            candle(300_000, 98.5, 102.5),  # both stop and TP2 touched in parent 5m
            candle(600_000, 90.0, 110.0),
        ]
        one = [
            candle(300_000, 99.7, 100.8),
            candle(360_000, 99.8, 102.1),  # TP2 first
            candle(420_000, 98.5, 102.2),  # stop touch occurs after exit and must be excluded
        ]

        def fake_market(symbol, interval, start, end):
            return (one, 'TEST_1M') if interval == '1' else (five, 'TEST_5M')

        ops.market_klines = fake_market
        out = ops.settle(episode('LONG'), ops.HORIZON_H * 3600_000)
        assert out['status'] == 'WIN_TP2'
        assert out['r_multiple'] == 2.0
        assert out['excursion_scope'] == 'THROUGH_TERMINAL_EVENT_1M'
        assert out['mae_r'] == 0.5
        assert out['mfe_r'] == 2.1
    finally:
        ops.market_klines = old_market
