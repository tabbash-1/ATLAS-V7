"""Daily context must be causal, legible, and never promote Production."""
import time
from unittest.mock import patch

import rc10_1_deep_analysis_overlay as deep

DAY = 86_400_000
HOUR = 3_600_000


def bars(step=DAY, n=90, asof=None):
    # All rows completed at the frozen as-of. No real market HTTP calls.
    asof = (int(time.time()*1000) // step)*step if asof is None else asof
    start = asof - n*step
    output=[]
    for i in range(n):
        p=100 + i*.55
        output.append({'open_time':start+i*step,'close_time':start+(i+1)*step-1,
                       'open':p-.2,'high':p+1.3,'low':p-1.3,
                       'close':p,'volume':100+i})
    return output


class MockAtlas:
    def __init__(self, raw=None):
        self.raw=raw
    def get_json_fallback(self, urls, label):
        if self.raw is not None:return self.raw
        interval=urls[0].split('interval=')[1].split('&')[0]
        step={'1h':HOUR,'4h':4*HOUR,'6h':6*HOUR,
              '12h':12*HOUR,'1d':DAY}[interval]
        return [[r['open_time'],str(r['open']),str(r['high']),str(r['low']),
                 str(r['close']),str(r['volume']),r['close_time']]
                for r in bars(step,220)]


def test_daily_context_alignment_and_prior_unseen_bar_geometry():
    d=bars()
    out=deep.daily_macro_context(d,'LONG')
    assert out['status']=='READY'
    assert out['bias']=='LONG'
    assert out['structural_trend']=='UPTREND'
    assert out['daily_phase']=='IMPULSE_UP'
    assert out['direction_alignment']=='WITH_DAILY'
    assert out['prior_20d_support']==min(x['low'] for x in d[-21:-1])
    assert out['prior_20d_resistance']==max(x['high'] for x in d[-21:-1])
    assert out['last_closed_day_end_ms']==d[-1]['close_time']
    assert out['daily_context_not_a_new_signal']
    assert not out['can_override_production']
    assert not out['can_change_threshold']
    assert not out['can_create_trade']
    short=deep.daily_macro_context(d,'SHORT')
    assert short['direction_alignment']=='COUNTER_DAILY'
    assert short['structural_trend']==out['structural_trend']


def test_future_daily_candle_excluded_from_daily_bias_and_levels():
    t = 1792300000000  # Fixed instant, with current UTC day incomplete
    boundary = t // DAY * DAY
    closed = bars(DAY, 80, asof=boundary)
    bad = {'open_time':boundary,'close_time':boundary+DAY-1,
           'open':1,'high':1,'low':.001,'close':.001,'volume':100000}
    raw=closed+[bad]
    atlas=MockAtlas([[r['open_time'],r['open'],r['high'],r['low'],
                      r['close'],r['volume'],r['close_time']] for r in raw])
    with patch.object(deep.time,'time',return_value=t/1000):
        out=deep._klines(atlas,'BTCUSDT','1d')
    assert len(out)==80
    assert out[-1]['close_time']==boundary-1
    clean=deep.daily_macro_context(out,'LONG')
    assert clean['bias']=='LONG'
    assert clean['close']==closed[-1]['close']
    assert clean['prior_20d_support']>1  # Extreme unfinished candle excluded


def test_incomplete_daily_history_must_not_fabricate_context():
    x=deep.daily_macro_context(bars(n=35),'SHORT')
    assert x['status']=='UNAVAILABLE' and x['direction_alignment']=='UNKNOWN'
    assert x['can_override_production'] is False


def test_deep_website_has_explicit_daily_context_no_extra_gate():
    atlas=MockAtlas()
    response=deep.analyze(atlas,'BTCUSDT')
    assert response['ok'] is True
    d=response['daily_context']
    assert d['status']=='READY'
    assert d['direction_alignment'] in ('WITH_DAILY','COUNTER_DAILY','NEUTRAL_DAILY',
                                        'NO_PROPOSED_DIRECTION')
    assert d['last_closed_day_end_ms']<=response['generated_at_ms']
    assert d['can_override_production'] is False
    assert d['can_change_threshold'] is False
    assert d['analysis_only'] is True
    assert response['research_only'] is True
    assert response['live_execution'] is False
    assert response['mtf_states']['1d']['bias']==d['bias']


if __name__=='__main__':
    test_daily_context_alignment_and_prior_unseen_bar_geometry()
    test_future_daily_candle_excluded_from_daily_bias_and_levels()
    test_incomplete_daily_history_must_not_fabricate_context()
    test_deep_website_has_explicit_daily_context_no_extra_gate()
    print('RC10 closed-daily context research tests: ok')
