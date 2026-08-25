import hype_market_data as spot
import futures_provider_chain as fpc


class Atlas:
    UA = 'test'

    def __init__(self):
        self.MARKET_DATA_STATE = {
            'spot': {'last_provider': None, 'last_success_at': None, 'last_error': None},
            'futures': {'last_provider': None, 'last_success_at': None, 'last_error': None},
        }
        self._spot_klines = lambda symbol, limit=220: (_ for _ in ()).throw(RuntimeError('primary down'))
        self.capture = lambda symbol: {'symbol': symbol, 'futures_evidence_validated': False, 'futures_provider': 'PRIMARY_SHADOW'}

    @staticmethod
    def now_iso():
        return '2026-08-25T00:00:00+00:00'


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


def test_hype_futures_upgrades_only_with_validated_cex_contract(monkeypatch):
    atlas = Atlas()
    monkeypatch.setattr(spot, '_persist_futures', lambda atlas, snap: None)

    validated = {
        'symbol': 'HYPEUSDT',
        'futures_provider': 'OKX_USDT_SWAP_PUBLIC',
        'futures_evidence_validated': True,
        'validation_contract': 'MARK_FUNDING_OI_BOOK_TAKER_FLOW_REQUIRED',
    }
    monkeypatch.setattr(fpc, '_okx_capture', lambda atlas, symbol: dict(validated))
    monkeypatch.setattr(fpc, '_bybit_capture', lambda atlas, symbol: (_ for _ in ()).throw(AssertionError('Bybit should not be needed')))

    state = spot._install_hype_futures_fallback(atlas)
    result = atlas.capture('HYPEUSDT')

    assert result['futures_evidence_validated'] is True
    assert result['futures_provider'] == 'OKX_USDT_SWAP_PUBLIC'
    assert state['validated_successes'] == 1
    assert atlas.MARKET_DATA_STATE['futures']['last_provider'] == 'OKX_USDT_SWAP_PUBLIC'


def test_hype_futures_preserves_unvalidated_primary_when_cex_contract_fails(monkeypatch):
    atlas = Atlas()
    primary = {'symbol': 'HYPEUSDT', 'futures_provider': 'PRIMARY_SHADOW', 'futures_evidence_validated': False}
    atlas.capture = lambda symbol: dict(primary)
    monkeypatch.setattr(spot, '_persist_futures', lambda atlas, snap: None)
    monkeypatch.setattr(fpc, '_okx_capture', lambda atlas, symbol: {'symbol': symbol, 'futures_evidence_validated': False})
    monkeypatch.setattr(fpc, '_bybit_capture', lambda atlas, symbol: (_ for _ in ()).throw(RuntimeError('unavailable')))

    state = spot._install_hype_futures_fallback(atlas)
    result = atlas.capture('HYPEUSDT')

    assert result == primary
    assert result['futures_evidence_validated'] is False
    assert state['validated_successes'] == 0
    assert state['last_error']


def test_non_hype_futures_capture_is_unchanged(monkeypatch):
    atlas = Atlas()
    calls = []
    atlas.capture = lambda symbol: calls.append(symbol) or {'symbol': symbol, 'futures_evidence_validated': True}
    spot._install_hype_futures_fallback(atlas)

    result = atlas.capture('BTCUSDT')
    assert result['symbol'] == 'BTCUSDT'
    assert calls == ['BTCUSDT']


if __name__ == '__main__':
    test_okx_symbol_mapping()
    print('spot/HYPE market-data resilience tests: ok')
