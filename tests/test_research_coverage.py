import research_coverage as rc


def row(symbol, score=55, direction='LONG'):
    return {'symbol': symbol, 'final_score': score, 'direction': direction}


def test_build_coverage_tracks_only_cloud_research_rows():
    now = 10 * 3600 * 1000
    rows = [
        {'symbol': 'BTCUSDT', 'captured_at_ms': 9 * 3600 * 1000, 'auto_source': 'CLOUD_FORWARD_ALPHA18'},
        {'symbol': 'BTCUSDT', 'captured_at_ms': 8 * 3600 * 1000, 'auto_source': 'MANUAL'},
        {'symbol': 'ETHUSDT', 'captured_at_ms': 1 * 3600 * 1000, 'research_sampling_lane': True},
    ]
    cov = rc.build_coverage(rows, ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'], now, stale_hours=8)
    assert cov['BTCUSDT']['observations'] == 1
    assert cov['BTCUSDT']['stale'] is False
    assert cov['ETHUSDT']['observations'] == 1
    assert cov['ETHUSDT']['stale'] is True
    assert cov['BNBUSDT']['never_seen'] is True


def test_choose_research_samples_prioritizes_never_seen_then_least_covered():
    pool = [row('BTCUSDT', 59), row('ETHUSDT', 51), row('BNBUSDT', 50), row('SOLUSDT', 58)]
    coverage = {
        'BTCUSDT': {'observations': 8, 'last_seen_ms': 9000},
        'ETHUSDT': {'observations': 0, 'last_seen_ms': None},
        'BNBUSDT': {'observations': 0, 'last_seen_ms': None},
        'SOLUSDT': {'observations': 2, 'last_seen_ms': 3000},
    }
    chosen = rc.choose_research_samples(pool, 2, set(), coverage)
    assert [x['symbol'] for x in chosen] == ['ETHUSDT', 'BNBUSDT']


def test_signal_selected_row_is_not_duplicated_in_research_lane():
    pool = [row('BTCUSDT', 59), row('ETHUSDT', 58)]
    coverage = {
        'BTCUSDT': {'observations': 0, 'last_seen_ms': None},
        'ETHUSDT': {'observations': 0, 'last_seen_ms': None},
    }
    chosen = rc.choose_research_samples(pool, 2, {('BTCUSDT', 'LONG')}, coverage)
    assert [x['symbol'] for x in chosen] == ['ETHUSDT']


def test_coverage_summary_reports_missing_and_stale_assets():
    cov = {
        'BTCUSDT': {'observations': 3, 'never_seen': False, 'stale': False},
        'ETHUSDT': {'observations': 1, 'never_seen': False, 'stale': True},
        'BNBUSDT': {'observations': 0, 'never_seen': True, 'stale': True},
    }
    summary = rc.coverage_summary(cov)
    assert summary['covered_assets'] == 2
    assert summary['total_assets'] == 3
    assert summary['never_seen_assets'] == ['BNBUSDT']
    assert summary['stale_assets'] == ['ETHUSDT']
    assert summary['complete'] is False
    assert summary['fresh'] is False


if __name__ == '__main__':
    test_build_coverage_tracks_only_cloud_research_rows()
    test_choose_research_samples_prioritizes_never_seen_then_least_covered()
    test_signal_selected_row_is_not_duplicated_in_research_lane()
    test_coverage_summary_reports_missing_and_stale_assets()
    print('research coverage tests: ok')
