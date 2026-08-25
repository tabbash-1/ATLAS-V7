import hype_market_data as spot


class Atlas:
    UA = 'test'
    MARKET_DATA_STATE = {'spot': {'last_provider': None, 'last_success_at': None, 'last_error': None}}

    def __init__(self):
        self._spot_klines = lambda symbol, limit=220: (_ for _ in ()).throw(RuntimeError('primary down'))

    @staticmethod
    def now_iso():
        return '2026-08-25T00:00:00+00:00'


def _rows(n=120):
    return [[str(i), '1', '2', '0.5', '1.5', '10'] for i in range(n)]


def test_okx_symbol_mapping():
    assert spot._okx_symbol('BTCUSDT') == 'BTC-USDT'
    assert spot._okx_symbol('BINANCE:HYPEUSDT') == 'HYPE-USDT'


def test_non_hype_uses_okx_only_after_primary_failure(monkeypatch):
    atlas = Atlas()

    def fake_okx(symbol, limit, ua):
        assert symbol == 'BTCUSDT'
        return [{'open_time': 1, 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10.0}] * limit, 'www.okx.com'

    monkeypatch.setattr(spot, '_okx', fake_okx)
    spot.install(atlas)
    rows = atlas._spot_klines('BTCUSDT', 100)
    assert len(rows) == 100
    assert atlas.MARKET_DATA_STATE['spot']['last_provider'] == 'www.okx.com'
    assert atlas.MARKET_DATA_STATE['spot']['last_error'] is None


def test_hype_does_not_call_binance_primary(monkeypatch):
    atlas = Atlas()
    called = {'okx': 0}

    def fake_okx(symbol, limit, ua):
        called['okx'] += 1
        return [{'open_time': 1, 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 10.0}] * limit, 'www.okx.com'

    monkeypatch.setattr(spot, '_okx', fake_okx)
    spot.install(atlas)
    rows = atlas._spot_klines('HYPEUSDT', 100)
    assert len(rows) == 100
    assert called['okx'] == 1


if __name__ == '__main__':
    test_okx_symbol_mapping()
    print('spot market-data resilience tests: ok')
