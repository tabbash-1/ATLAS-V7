#!/usr/bin/env python3
import prospective_long_close_shadow as s


def _row(direction='LONG'):
    return {
        'symbol': 'BTCUSDT',
        'direction': direction,
        'final_score': 72,
        'production_signal_qualified': True,
        'direction_votes': 3,
        'structural_obstacle_price': 100.0,
        'score_attribution': {
            'trend_base': 64,
            'obstacle_reason': 'CLOSE_PRIOR_STRUCTURE',
        },
    }


def _klines(closed_close, current_close, start=98.0):
    rows = []
    for i in range(18):
        px = start + i * 0.05
        rows.append({'open': px, 'high': px + 0.2, 'low': px - 0.2, 'close': px})
    rows[-2] = {'open': closed_close - 0.1, 'high': closed_close + 0.2, 'low': closed_close - 0.2, 'close': closed_close}
    rows[-1] = {'open': current_close - 0.1, 'high': current_close + 0.2, 'low': current_close - 0.2, 'close': current_close}
    return rows


def test_unconfirmed_long_structure_is_shadow_veto_only():
    row = _row('LONG')
    r = s.combined_shadow_from_row(row, 68, _klines(99.95, 100.05))
    assert r['production_qualified'] is True
    assert r['fourth_vote_shadow_qualified'] is True
    assert r['structure_confirmation']['state'] == 'UNCONFIRMED_STRUCTURE_BREAK'
    assert r['structure_confirmation_veto'] is True
    assert r['long_close_structure_veto'] is True
    assert r['combined_shadow_qualified'] is False
    assert r['can_override_production'] is False
    assert r['production_threshold_changed'] is False
    assert r['production_scoring_changed'] is False
    assert r['live_execution'] is False


def test_confirmed_long_close_and_hold_remains_shadow_qualified():
    row = _row('LONG')
    r = s.combined_shadow_from_row(row, 68, _klines(100.30, 100.10))
    assert r['structure_confirmation']['closed_break_confirmed'] is True
    assert r['structure_confirmation']['hold_confirmed'] is True
    assert r['structure_confirmation']['confirmed'] is True
    assert r['structure_confirmation']['state'] == 'CONFIRMED_CLOSE_HOLD'
    assert r['structure_confirmation_veto'] is False
    assert r['combined_shadow_qualified'] is True


def test_short_side_is_symmetric_and_requires_break_below_support():
    row = _row('SHORT')
    r_bad = s.combined_shadow_from_row(row, 68, _klines(100.05, 99.95, start=102.0))
    assert r_bad['structure_confirmation_veto'] is True
    assert r_bad['long_close_structure_veto'] is False
    assert r_bad['combined_shadow_qualified'] is False

    r_ok = s.combined_shadow_from_row(row, 68, _klines(99.70, 99.90, start=102.0))
    assert r_ok['structure_confirmation']['confirmed'] is True
    assert r_ok['structure_confirmation_veto'] is False
    assert r_ok['combined_shadow_qualified'] is True


def test_non_close_structure_is_not_vetoed():
    row = _row('LONG')
    row['score_attribution']['obstacle_reason'] = 'CLEAR_STRUCTURE'
    r = s.combined_shadow_from_row(row, 68, _klines(99.0, 99.0))
    assert r['structure_confirmation']['relevant'] is False
    assert r['structure_confirmation']['state'] == 'NOT_APPLICABLE'
    assert r['structure_confirmation_veto'] is False
    assert r['combined_shadow_qualified'] is True


def test_missing_market_evidence_fails_closed_only_inside_shadow():
    row = _row('LONG')
    r = s.combined_shadow_from_row(row, 68)
    assert r['structure_confirmation']['state'] == 'UNKNOWN_NO_MARKET_EVIDENCE'
    assert r['structure_confirmation_veto'] is True
    assert r['production_qualified'] is True
    assert r['can_override_production'] is False


def main():
    test_unconfirmed_long_structure_is_shadow_veto_only()
    test_confirmed_long_close_and_hold_remains_shadow_qualified()
    test_short_side_is_symmetric_and_requires_break_below_support()
    test_non_close_structure_is_not_vetoed()
    test_missing_market_evidence_fails_closed_only_inside_shadow()
    print('prospective structure confirmation shadow tests: ok')


if __name__ == '__main__':
    main()
