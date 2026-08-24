import trade_outcome_ledger as ledger


def row(**extra):
    base = {
        'id': 'x1',
        'captured_at': '2026-08-23T00:00:00+00:00',
        'captured_at_ms': 1000,
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100,
        'champion_take': True,
        'champion_score': 80,
        'final_score': 80,
        'forward_return_pct': {'1': 1.0, '4': 2.0, '12': -1.0, '24': 3.0},
    }
    base.update(extra)
    return base


def test_long_positive_is_win_and_negative_is_loss():
    assert ledger.classify_row(row(), 24)['outcome'] == 'WIN'
    assert ledger.classify_row(row(), 12)['outcome'] == 'LOSS'


def test_short_inverts_market_return():
    x = ledger.classify_row(row(direction='SHORT', forward_return_pct={'24': -2.5}), 24)
    assert x['outcome'] == 'WIN'
    assert x['directional_return_pct'] == 2.5


def test_unmatured_is_open():
    x = ledger.classify_row(row(forward_return_pct={}), 24)
    assert x['outcome'] == 'OPEN'


def test_signal_scope_is_production_threshold_not_research_champion():
    rows = [
        row(id='production', final_score=70, champion_score=70, champion_take=True),
        row(id='research_champion', captured_at_ms=1100, final_score=65, champion_score=65, champion_take=True),
        row(id='research_sample', captured_at_ms=1200, final_score=55, champion_score=55, champion_take=False, research_sampling_lane=True),
    ]
    signals = ledger.build_ledger(rows, horizon=24, scope='signals')
    champions = ledger.build_ledger(rows, horizon=24, scope='champions')
    all_rows = ledger.build_ledger(rows, horizon=24, scope='all')
    assert [x['id'] for x in signals] == ['production']
    assert {x['id'] for x in champions} == {'production', 'research_champion'}
    assert len(all_rows) == 3


def test_explicit_production_flag_wins_over_legacy_score_fallback():
    x = row(final_score=80, production_signal_qualified=False, signal_threshold=68)
    assert ledger.is_production_signal(x) is False
    assert ledger.classify_row(x, 24)['signal_qualified'] is False


def test_summary_win_rate_uses_decisive_closed_only():
    rows = [
        row(id='w', forward_return_pct={'24': 2}),
        row(id='l', captured_at_ms=1100, forward_return_pct={'24': -1}),
        row(id='o', captured_at_ms=1200, forward_return_pct={}),
    ]
    s = ledger.summarize(rows, 24, 'signals')
    assert s['overall']['wins'] == 1
    assert s['overall']['losses'] == 1
    assert s['overall']['open'] == 1
    assert s['overall']['win_rate_pct'] == 50.0
    assert s['r_multiple_available'] is False


if __name__ == '__main__':
    test_long_positive_is_win_and_negative_is_loss()
    test_short_inverts_market_return()
    test_unmatured_is_open()
    test_signal_scope_is_production_threshold_not_research_champion()
    test_explicit_production_flag_wins_over_legacy_score_fallback()
    test_summary_win_rate_uses_decisive_closed_only()
    print('trade outcome ledger tests: ok')
