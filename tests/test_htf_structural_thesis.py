import math

from htf_structural_thesis import analyze_frame, analyze_frames


def series(direction='LONG', n=120, start=100.0, step=0.35):
    out = []
    for i in range(n):
        trend = i * step if direction == 'LONG' else -i * step
        wave = math.sin(i / 3.0) * 0.7
        c = start + trend + wave
        out.append({'time': i, 'open': c - 0.1, 'high': c + 0.8, 'low': c - 0.8, 'close': c, 'volume': 100 + i})
    return out


def structural_series(direction='LONG', n=120, start=100.0):
    out=[]
    for i in range(n):
        trend=(i*0.25) if direction=='LONG' else -(i*0.25)
        wave=math.sin(i/3.0)*2.0
        c=start+trend+wave
        out.append({'time':i,'open':c-0.1,'high':c+0.8,'low':c-0.8,'close':c,'volume':100+i})
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
    assert row['analysis_model_version'] == 'ATLAS_MARKET_INTELLIGENCE_V1'


def test_frame_exposes_structure_and_current_phase_separately():
    row=analyze_frame(structural_series('LONG'),'4h')
    assert row['structural_direction']=='LONG'
    assert row['current_phase'] in ('BULLISH_EXPANSION','BEARISH_CORRECTION','CONSOLIDATION_OR_TRANSITION')
    assert row['impulse'] in ('BULLISH','BEARISH','NEUTRAL')
    assert row['trend_health'] in ('CONFIRMED','DETERIORATING','STABLE')
    assert 'relative_volume' in row
    assert 'return_3_bars_pct' in row


def test_bullish_structure_can_report_bearish_correction_without_relabeling_structure():
    rows=structural_series('LONG',140)
    # Controlled late selloff: enough to establish a bearish current impulse while
    # preserving the previously established higher-timeframe swing structure.
    last=rows[-7]['close']
    for j in range(6):
        c=last-(j+1)*1.1
        rows[-6+j]={'time':140-6+j,'open':c+0.5,'high':c+0.8,'low':c-0.8,'close':c,'volume':400+j*40}
    row=analyze_frame(rows,'4h')
    assert row['impulse']=='BEARISH'
    if row['structural_direction']=='LONG':
        assert row['current_phase']=='BEARISH_CORRECTION'
        assert row['trend_health']=='DETERIORATING'


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
    f=frames(); f['1d']=structural_series('SHORT')
    row = analyze_frames(f, 'LONG')
    assert row['daily_context'] == 'SHORT'
    assert row['daily_context_confidence'] == 'STRONG'
    assert row['status'] == 'WAIT'
    assert row['reason'] == '1D_MACRO_STRONGLY_OPPOSES_HTF'
    assert row['product_direction'] == 'LONG'
    assert row['direction'] == 'LONG'


def test_trend_only_daily_opposition_is_context_not_blanket_veto():
    row=analyze_frames(frames(d1='SHORT'),'LONG')
    assert row['daily_context']=='SHORT'
    assert row['daily_context_confidence']=='TREND_ONLY'
    assert row['status']=='PASS'
    assert row['product_direction']=='LONG'


def test_incomplete_htf_data_fails_closed():
    f = frames(); f['12h'] = f['12h'][:20]
    row = analyze_frames(f, 'LONG')
    assert row['status'] == 'BLOCK'
    assert row['product_direction'] is None
    assert '12h' in row['missing_timeframes']
