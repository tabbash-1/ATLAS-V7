import copy

import historical_microstructure_replay as r


def smart(ts, price, oi, taker=1.10, imb=0.08, funding=0.0001):
    return {
        'captured_at_ms': ts,
        'symbol': 'BTCUSDT',
        'mark_price': price,
        'open_interest': oi,
        'funding_rate': funding,
        'taker_ratio': taker,
        'orderbook_imbalance': imb,
        'futures_provider': 'OKX_USDT_SWAP_PUBLIC',
        'futures_evidence_validated': True,
    }


def forward(ts=10_000_000):
    return {
        'id': 'f1', 'captured_at_ms': ts, 'symbol': 'BTCUSDT',
        'direction': 'LONG', 'entry': 100.0, 'final_score': 72,
        'regime': 'TREND_UP', 'rr_tp2': 1.8,
        'forward_return_pct': {'1': 99.0, '24': -99.0},
    }


def history(ts=10_000_000):
    # Enough same-provider validated prior snapshots for 4h/12h windows.
    step = 60 * 60 * 1000
    return [smart(ts - i*step, 100-i*0.4, 1000-i*8) for i in range(11, -1, -1)]


def test_future_snapshot_never_changes_replay():
    f = forward()
    base = history()
    a = r.report([f], base)
    future = smart(f['captured_at_ms'] + 1, 500, 999999, taker=0.1, imb=-0.9, funding=-0.01)
    b = r.report([f], base + [future])
    assert a['rows'] == b['rows']
    assert a['feature_dataset_sha256'] == b['feature_dataset_sha256']
    assert a['future_data_allowed'] is False


def test_outcome_field_never_changes_feature_hash():
    f1 = forward()
    f2 = copy.deepcopy(f1)
    f2['forward_return_pct'] = {'1': -1234, '12': 4567}
    f2['settled'] = 'WIN'
    a = r.report([f1], history())
    b = r.report([f2], history())
    assert a['feature_dataset_sha256'] == b['feature_dataset_sha256']
    assert a['outcomes_read'] is False
    assert a['forward_return_fields_read'] is False


def test_replay_is_explicitly_not_forward_proof():
    x = r.report([forward()], history())
    assert x['retrospective_reconstruction'] is True
    assert x['forward_proof_equivalent'] is False
    assert x['backfill_claimed_as_frozen_forward'] is False


if __name__ == '__main__':
    test_future_snapshot_never_changes_replay()
    test_outcome_field_never_changes_feature_hash()
    test_replay_is_explicitly_not_forward_proof()
    print('historical microstructure replay tests: OK')
