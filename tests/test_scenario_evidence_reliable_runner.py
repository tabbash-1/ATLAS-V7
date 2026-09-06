import scenario_evidence_reliable_runner as r


def _decision(symbol):
    return {'ok': True, 'symbol': symbol, 'htf_scenario_engine': {'readiness': 'WAIT_FOR_HTF_ALIGNMENT'}}


def test_retry_recovers_after_transient_failures():
    calls = {'n': 0}
    original = r.p.fetch_decision
    try:
        def flaky(symbol):
            calls['n'] += 1
            if calls['n'] < 3:
                raise RuntimeError('502')
            return _decision(symbol)
        r.p.fetch_decision = flaky
        out = r.fetch_decision_retry('BTCUSDT', delays=(0, 0, 0), sleeper=lambda _: None)
        assert out['symbol'] == 'BTCUSDT'
        assert calls['n'] == 3
    finally:
        r.p.fetch_decision = original


def test_total_failure_does_not_save():
    saved = {'n': 0}
    original_symbols = r.p.SYMBOLS
    original_load = r.p.load_records
    try:
        r.p.SYMBOLS = ('BTCUSDT', 'ETHUSDT')
        r.p.load_records = lambda: []
        def fail(symbol):
            raise RuntimeError('502')
        def saver(*args, **kwargs):
            saved['n'] += 1
        try:
            r.run_once(fetcher=fail, saver=saver)
            raise AssertionError('expected RuntimeError')
        except RuntimeError as exc:
            assert 'zero successful ATLAS decision reads' in str(exc)
        assert saved['n'] == 0
    finally:
        r.p.SYMBOLS = original_symbols
        r.p.load_records = original_load


def test_partial_success_is_explicit_and_saved():
    saved = {}
    original_symbols = r.p.SYMBOLS
    original_load = r.p.load_records
    original_settle = r.p.settle_record
    try:
        r.p.SYMBOLS = ('BTCUSDT', 'ETHUSDT')
        r.p.load_records = lambda: []
        r.p.settle_record = lambda row, now=None: row
        def fetcher(symbol):
            if symbol == 'ETHUSDT':
                raise RuntimeError('502')
            return _decision(symbol)
        def saver(rows, snap):
            saved['snap'] = snap
        out = r.run_once(fetcher=fetcher, saver=saver)
        c = out['collector']
        assert c['successful_decisions'] == 1
        assert c['failed_decisions'] == 1
        assert c['coverage_pct'] == 50.0
        assert c['collector_status'] == 'PARTIAL'
        assert saved['snap'] is out
    finally:
        r.p.SYMBOLS = original_symbols
        r.p.load_records = original_load
        r.p.settle_record = original_settle


def test_full_coverage_status():
    assert r.coverage(7, 7) == ('FULL', 100.0)
    assert r.coverage(0, 7) == ('FAILED', 0.0)


if __name__ == '__main__':
    test_retry_recovers_after_transient_failures()
    test_total_failure_does_not_save()
    test_partial_success_is_explicit_and_saved()
    test_full_coverage_status()
    print('scenario evidence reliable runner tests: OK')
