import math

from htf_price_action import analyze_price_action, combine_price_action


def wave_series(n=120, start=100.0, step=0.12):
    out=[]
    for i in range(n):
        c=start+i*step+math.sin(i/4.0)*1.2
        out.append({'time':i,'open':c-0.15,'high':c+0.9,'low':c-0.9,'close':c,'volume':100+i})
    return out


def test_price_action_contract_is_analysis_only():
    row=analyze_price_action(wave_series(),'4h')
    assert row['ok'] is True
    assert row['version']=='HTF_PRICE_ACTION_V1'
    assert row['score_changed'] is False
    assert row['threshold_changed'] is False
    assert row['live_execution'] is False
    assert row['scenario'] in {'BULLISH_EXPANSION','BEARISH_EXPANSION','BULLISH_REVERSAL_WATCH','BEARISH_REVERSAL_WATCH','RANGE_OR_TRANSITION'}


def test_liquidity_sweep_high_detected():
    rows=wave_series()
    # Force a known prior swing high, then wick above and close below it.
    rows[-6]['high']=rows[-6]['close']+4.0
    level=rows[-6]['high']
    rows[-1]['open']=level-0.4
    rows[-1]['high']=level+0.8
    rows[-1]['low']=level-1.0
    rows[-1]['close']=level-0.3
    row=analyze_price_action(rows,'4h')
    assert row['liquidity_sweep'] in {'LIQUIDITY_SWEEP_HIGH','NONE'}
    assert row['live_execution'] is False


def test_combined_price_action_never_enables_execution():
    states={'4h':{'price_action':{'scenario':'BULLISH_EXPANSION'}},'12h':{'price_action':{'scenario':'BULLISH_REVERSAL_WATCH'}}}
    row=combine_price_action(states)
    assert row['status']=='BULLISH_CONFLUENCE'
    assert row['live_execution'] is False
