import historical_source_runtime as h


class A:
    def __init__(self, forward, smart):
        self._f = forward
        self._s = smart
    def read_forward(self): return self._f
    def read_all(self): return self._s
    def now_iso(self): return '2026-08-26T00:00:00+00:00'


def fwd(ts=10_000_000):
    return {
        'id':'f1','captured_at_ms':ts,'captured_at':'x','symbol':'BTCUSDT',
        'direction':'LONG','entry':100,'champion_score':70,'regime':'TREND_UP',
        # Deliberately present: the audit must never consume/copy this field.
        'forward_return_pct': {'1': 99.0, '24': -99.0},
    }


def sm(ts, validated=True):
    return {
        'captured_at_ms':ts,'captured_at':'x','symbol':'BTCUSDT','funding_rate':0.001,
        'open_interest':1000,'oi_change_pct':1.2,'taker_ratio':1.4,
        'orderbook_imbalance':0.15,'futures_provider':'OKX_USDT_SWAP_PUBLIC',
        'futures_evidence_validated':validated,
    }


def test_uses_only_prior_smart_money_and_never_forward_returns():
    a=A([fwd()], [sm(9_000_000, True), sm(10_000_001, False)])
    r=h.build_report(a, max_smart_age_ms=2_000_000)
    assert r['prior_context_join']['matched_forward_rows'] == 1
    assert r['prior_context_join']['validated_futures_context_rows'] == 1
    assert r['future_smart_money_match_allowed'] is False
    assert r['outcomes_read'] is False
    assert r['forward_return_fields_read'] is False
    assert 'forward_return_pct' not in r['forward']['field_coverage']


def test_future_only_context_does_not_match():
    a=A([fwd()], [sm(10_000_001)])
    r=h.build_report(a, max_smart_age_ms=2_000_000)
    assert r['prior_context_join']['matched_forward_rows'] == 0


def test_stale_prior_context_does_not_match():
    a=A([fwd()], [sm(1_000_000)])
    r=h.build_report(a, max_smart_age_ms=1000)
    assert r['prior_context_join']['matched_forward_rows'] == 0


def test_replay_is_not_forward_proof():
    rows=[dict(fwd(10_000_000+i*1000), id=f'f{i}') for i in range(100)]
    a=A(rows, [sm(9_999_999)])
    r=h.build_report(a, max_smart_age_ms=5_000_000)
    assert r['replay_classification']['historical_backtest_possible'] is True
    assert r['replay_classification']['forward_proof_equivalent'] is False


if __name__ == '__main__':
    test_uses_only_prior_smart_money_and_never_forward_returns()
    test_future_only_context_does_not_match()
    test_stale_prior_context_does_not_match()
    test_replay_is_not_forward_proof()
    print('historical source runtime safety tests: OK')
