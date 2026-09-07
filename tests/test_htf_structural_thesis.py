import math

from htf_structural_thesis import analyze_frames


def series(direction='LONG', n=120, start=100.0, step=0.35):
    out = []
    for i in range(n):
        trend = i * step if direction == 'LONG' else -i * step
        wave = math.sin(i / 3.0) * 0.7
        c = start + trend + wave
        out.append({'time': i, 'open': c - 0.1, 'high': c + 0.8, 'low': c - 0.8, 'close': c, 'volume': 100 + i})
    return out


def frames(h1='LONG', h4='LONG', h12='LONG', d1='LONG'):
    return {'1h': series(h1), '4h': series(h4), '12h': series(h12), '1d': series(d1)}


def test_aligned_htf_and_one_hour_pass():
    row = analyze_frames(frames(), 'LONG')
    assert row['status'] == 'PASS'
    assert row['direction'] == 'LONG'
    assert row['product_direction'] == 'LONG'
    assert row['entry_confirmation_direction'] == 'LONG'
    assert row['direction_alignment'] == 'ALIGNED'


def test_one_hour_cannot_flip_higher_timeframe_thesis():
    row = analyze_frames(frames(h1='SHORT'), 'SHORT')
    assert row['status'] == 'WAIT'
    assert row['direction'] == 'LONG'
    assert row['product_direction'] == 'LONG'
    assert row['entry_confirmation_direction'] == 'SHORT'
    assert row['direction_alignment'] == 'OPPOSED'
    assert row['can_flip_from_1h_only'] is False


def test_entry_confirmation_direction_cannot_override_higher_timeframes():
    row = analyze_frames(frames(), 'SHORT')
    assert row['status'] == 'WAIT'
    assert row['reason'] == 'ENTRY_CONFIRMATION_OPPOSES_PRODUCT_DIRECTION'
    assert row['product_direction'] == 'LONG'
    assert row['entry_confirmation_direction'] == 'SHORT'


def test_4h_12h_conflict_fails_to_wait_without_product_direction():
    row = analyze_frames(frames(h4='LONG', h12='SHORT'), 'LONG')
    assert row['status'] == 'WAIT'
    assert row['direction'] is None
    assert row['product_direction'] is None
    assert row['reason'] == '4H_12H_NOT_ALIGNED'


def test_strong_daily_opposition_is_macro_veto_not_direction_flip():
    row = analyze_frames(frames(d1='SHORT'), 'LONG')
    assert row['status'] == 'WAIT'
    assert row['reason'] == '1D_MACRO_STRONGLY_OPPOSES_HTF'
    assert row['daily_context'] == 'SHORT'
    assert row['product_direction'] == 'LONG'
    assert row['direction'] == 'LONG'


def test_incomplete_htf_data_fails_closed():
    f = frames()
    f['12h'] = f['12h'][:20]
    row = analyze_frames(f, 'LONG')
    assert row['status'] == 'BLOCK'
    assert row['product_direction'] is None
    assert '12h' in row['missing_timeframes']
