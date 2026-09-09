import execution_cost_model as ecm


def fake_getter(url, ua):
    if 'public/instruments' in url:
        return {
            'code': '0',
            'data': [{
                'instId': 'BTC-USDT-SWAP',
                'ctVal': '0.01',
                'ctValCcy': 'BTC',
                'ctType': 'linear',
                'settleCcy': 'USDT',
            }],
        }
    if 'market/books' in url:
        return {
            'code': '0',
            'data': [{
                'bids': [['99.9', '100'], ['99.8', '100']],
                'asks': [['100.1', '100'], ['100.2', '100']],
            }],
        }
    raise AssertionError(url)


def test_unconfigured_fee_fails_closed(monkeypatch):
    monkeypatch.delenv('ATLAS_EXECUTION_TAKER_FEE_BPS', raising=False)
    out = ecm.estimate(
        'BTCUSDT', notional_usdt=50, venue='OKX_USDT_SWAP',
        taker_fee_bps=None, getter=fake_getter,
    )
    assert out['fee_bps'] is None
    assert out['validated'] is False
    assert 'TAKER_FEE_NOT_CONFIGURED' in out['blockers']


def test_complete_live_cost_contract_can_validate():
    out = ecm.estimate(
        'BTCUSDT', notional_usdt=50, venue='OKX_USDT_SWAP',
        taker_fee_bps=5.0, getter=fake_getter,
    )
    assert out['validated'] is True
    assert out['spread_bps'] > 0
    assert out['fee_bps'] == 5.0
    assert out['slippage_bps'] >= 0
    assert out['round_trip_cost_bps'] == 2 * (out['fee_bps'] + out['spread_bps'] + out['slippage_bps'])
    assert out['buy_quote_filled'] == 50
    assert out['sell_quote_filled'] == 50


def test_wrong_venue_cannot_validate():
    out = ecm.estimate(
        'BTCUSDT', notional_usdt=50, venue='SOMETHING_ELSE',
        taker_fee_bps=5.0, getter=fake_getter,
    )
    assert out['validated'] is False
    assert 'EXECUTION_VENUE_NOT_CONFIGURED' in out['blockers']


def test_insufficient_depth_is_not_extrapolated():
    out = ecm.estimate(
        'BTCUSDT', notional_usdt=100000, venue='OKX_USDT_SWAP',
        taker_fee_bps=5.0, getter=fake_getter,
    )
    assert out['validated'] is False
    assert 'INSUFFICIENT_L2_DEPTH_FOR_NOTIONAL' in out['blockers']


def test_round_trip_cost_to_net_r_uses_frozen_geometry():
    out = ecm.apply_cost_to_r(
        2.0,
        entry=100.0,
        risk_abs=1.0,
        fee_bps=5.0,
        spread_bps=1.0,
        slippage_bps=2.0,
    )
    assert out['round_trip_cost_bps'] == 16.0
    assert out['execution_cost_r'] == 0.16
    assert out['net_r'] == 1.84
    assert out['validated_cost_inputs'] is True


def test_missing_cost_component_fails_closed_for_net_r():
    out = ecm.apply_cost_to_r(
        -1.0,
        entry=100.0,
        risk_abs=1.0,
        fee_bps=5.0,
        spread_bps=None,
        slippage_bps=2.0,
    )
    assert out['gross_r'] == -1.0
    assert out['net_r'] is None
    assert out['execution_cost_r'] is None
    assert out['validated_cost_inputs'] is False
