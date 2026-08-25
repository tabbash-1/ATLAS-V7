import microstructure_memory as mm

NOW = 1_800_000_000_000
HOUR = 3_600_000


def row(i, *, provider='OKX_USDT_SWAP_PUBLIC', price=100.0, oi=1000.0,
        funding=0.0001, taker=1.10, book=0.08, symbol='BTCUSDT', validated=True):
    return {
        'schema': 'ATLAS_SM_V2',
        'symbol': symbol,
        'captured_at_ms': NOW - (12 - i) * HOUR,
        'mark_price': price,
        'open_interest': oi,
        'funding_rate': funding,
        'taker_ratio': taker,
        'orderbook_imbalance': book,
        'futures_provider': provider,
        'futures_evidence_validated': validated,
    }


def test_long_accumulation_detected_from_same_provider_history():
    rows = [
        row(i, price=100 + i * .35, oi=1000 + i * 12, taker=1.12, book=.09)
        for i in range(1, 13)
    ]
    out = mm.summarize_window(rows, 12, now_ms=NOW)
    assert out['status'] == 'READY'
    assert out['provider_lineage_safe'] is True
    assert out['price_change_pct'] > 0
    assert out['open_interest_change_pct'] > 0
    assert out['label'] in ('LONG_ACCUMULATION', 'CROWDED_LONG_BUILDUP')


def test_provider_change_never_compares_open_interest_units():
    rows = []
    # Old provider has huge OI units that must never be compared to OKX units.
    # Keep six latest OKX rows so the 12h same-provider minimum is satisfied and
    # we can verify the actual OI delta is computed only within that lineage.
    for i in range(1, 7):
        rows.append(row(i, provider='BYBIT_LINEAR_PUBLIC', price=100+i*.1, oi=1_000_000+i*1000))
    for i in range(7, 13):
        rows.append(row(i, provider='OKX_USDT_SWAP_PUBLIC', price=101+i*.1, oi=1000+i*10))
    out = mm.summarize_window(rows, 12, now_ms=NOW)
    assert out['status'] == 'READY'
    assert out['provider'] == 'OKX_USDT_SWAP_PUBLIC'
    assert out['rows'] == 6
    assert out['validated_rows_all_providers'] > out['rows']
    assert abs(out['open_interest_change_pct']) < 10


def test_insufficient_latest_provider_lineage_fails_closed():
    rows = [row(i, provider='BYBIT_LINEAR_PUBLIC') for i in range(1, 11)]
    rows += [row(11, provider='OKX_USDT_SWAP_PUBLIC'), row(12, provider='OKX_USDT_SWAP_PUBLIC')]
    out = mm.summarize_window(rows, 12, now_ms=NOW)
    assert out['status'] == 'INSUFFICIENT'
    assert out['reason'] == 'INSUFFICIENT_SAME_PROVIDER_LINEAGE'


def test_unvalidated_rows_are_excluded():
    rows = [row(i, validated=False) for i in range(1, 13)]
    out = mm.summarize_window(rows, 12, now_ms=NOW)
    assert out['status'] == 'INSUFFICIENT'
    assert out['reason'] == 'NO_VALIDATED_ROWS'


def test_consensus_requires_multiple_ready_windows():
    rows = [
        row(i, price=100 + i * .4, oi=1000 + i * 15, taker=1.15, book=.10)
        for i in range(-12, 13)
    ]
    out = mm.analyze('BTCUSDT', rows, now_ms=NOW)
    assert out['sampling_contract'] == 'HOURLY_ARCHIVE_ONLY_NO_FAKE_INTRABAR_MEMORY'
    assert out['ready_windows'] >= 2
    assert out['consensus'] in ('BULLISH_FLOW', 'LONG_CROWDING_RISK')
    assert out['can_override_production'] is False
