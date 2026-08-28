import smart_money_shadow as sm


def row(**extra):
    base = {
        'symbol': 'BTCUSDT',
        'captured_at': '2026-08-29T00:00:00+03:00',
        'captured_at_ms': 1000,
        'direction': 'LONG',
        'futures_available': True,
        'taker_ratio': 1.12,
        'orderbook_imbalance': 0.18,
        'oi_change_pct': 1.5,
        'funding_rate': 0.0,
        'forward_return_pct': {'24': 2.0},
    }
    base.update(extra)
    return base


def test_long_shadow_requires_two_aligned_votes():
    x = sm.classify(row())
    assert x['shadow_direction'] == 'LONG'
    assert x['eligible_for_evaluation'] is True
    assert x['production_changed'] is False


def test_single_vote_stays_neutral():
    x = sm.classify(row(taker_ratio=1.12, orderbook_imbalance=0.0, oi_change_pct=0.0))
    assert x['shadow_direction'] == 'NEUTRAL'
    assert x['eligible_for_evaluation'] is False


def test_unvalidated_futures_never_enters_evaluation_cohort():
    x = sm.classify(row(futures_available=False, futures_shadow_validated=False))
    assert x['shadow_direction'] == 'LONG'
    assert x['eligible_for_evaluation'] is False


def test_short_shadow_inverts_forward_return():
    x = sm.evaluate(row(
        direction='SHORT',
        taker_ratio=0.88,
        orderbook_imbalance=-0.2,
        forward_return_pct={'24': -3.0},
    ), 24)
    assert x['shadow_direction'] == 'SHORT'
    assert x['shadow_directional_return_pct'] == 3.0
    assert x['shadow_outcome'] == 'WIN'


def test_summary_is_read_only_and_reports_alignment():
    s = sm.summarize([
        row(),
        row(direction='SHORT', taker_ratio=0.88, orderbook_imbalance=-0.2, forward_return_pct={'24': -1.0}),
    ], 24)
    assert s['decisive'] == 2
    assert s['wins'] == 2
    assert s['win_rate_pct'] == 100.0
    assert s['aligned_with_production'] == 2
    assert s['production_changed'] is False
    assert s['promotion_decision'] == 'NOT_AUTOMATED'


if __name__ == '__main__':
    test_long_shadow_requires_two_aligned_votes()
    test_single_vote_stays_neutral()
    test_unvalidated_futures_never_enters_evaluation_cohort()
    test_short_shadow_inverts_forward_return()
    test_summary_is_read_only_and_reports_alignment()
    print('smart money shadow tests: ok')
