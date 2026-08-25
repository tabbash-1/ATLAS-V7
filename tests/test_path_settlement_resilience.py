import urllib.error

import trade_path_settlement as tps


def reset_circuit():
    with tps._MARKET_DATA_CIRCUIT_LOCK:
        tps._MARKET_DATA_CIRCUIT.update({'open_until': 0.0, 'last_error': None, 'failures': 0, 'opened_at': None})


def test_provider_failure_opens_circuit_and_next_call_fails_fast():
    reset_circuit()
    calls = {'n': 0}
    original = tps.urllib.request.urlopen

    def fail(*args, **kwargs):
        calls['n'] += 1
        raise urllib.error.URLError('blocked for test')

    tps.urllib.request.urlopen = fail
    try:
        try:
            tps._request_klines('BTCUSDT', '5m', 1_000_000, 1_300_000, 10)
            raise AssertionError('first request should fail')
        except RuntimeError as exc:
            assert 'all spot candle providers failed' in str(exc)
        assert calls['n'] == 3
        try:
            tps._request_klines('ETHUSDT', '5m', 1_000_000, 1_300_000, 10)
            raise AssertionError('second request should fail fast')
        except RuntimeError as exc:
            assert 'market data circuit open' in str(exc)
        assert calls['n'] == 3
        state = tps.market_data_circuit_state()
        assert state['open'] is True
        assert state['failures'] == 1
    finally:
        tps.urllib.request.urlopen = original
        reset_circuit()


def test_summary_reports_market_data_errors_without_crashing():
    items = [
        {'terminal': False, 'path_outcome': 'MARKET_DATA_ERROR', 'geometry_status': 'FROZEN', 'production_signal_qualified': True},
        {'terminal': True, 'path_outcome': 'LOSS', 'r_multiple': -1.0, 'geometry_status': 'FROZEN', 'production_signal_qualified': True},
    ]
    summary = tps.summarize_path(items)
    assert summary['market_data_errors'] == 1
    assert summary['losses'] == 1
    assert 'market_data_circuit' in summary


if __name__ == '__main__':
    test_provider_failure_opens_circuit_and_next_call_fails_fast()
    test_summary_reports_market_data_errors_without_crashing()
    print('path settlement resilience tests: ok')
