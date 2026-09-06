"""Higher-timeframe price-action enrichment for ATLAS 4-12H analysis.

Pure analysis module: no score/threshold mutation and no live execution.
"""
from __future__ import annotations

VERSION = "HTF_PRICE_ACTION_V1"


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _atr(rows, n=14):
    if len(rows) <= n:
        return None
    trs=[]
    for i in range(len(rows)-n, len(rows)):
        h=_f(rows[i].get('high')); l=_f(rows[i].get('low')); pc=_f(rows[i-1].get('close'))
        if h is None or l is None or pc is None: continue
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs)/len(trs) if trs else None


def _swings(rows,left=2,right=2):
    highs=[]; lows=[]
    for i in range(left,len(rows)-right):
        h=_f(rows[i].get('high')); l=_f(rows[i].get('low'))
        if h is not None:
            peers=[_f(rows[j].get('high'),h) for j in range(i-left,i+right+1) if j!=i]
            if all(h>=x for x in peers): highs.append({'index':i,'price':h,'time':rows[i].get('time')})
        if l is not None:
            peers=[_f(rows[j].get('low'),l) for j in range(i-left,i+right+1) if j!=i]
            if all(l<=x for x in peers): lows.append({'index':i,'price':l,'time':rows[i].get('time')})
    return highs,lows


def _cluster_levels(levels,tolerance):
    out=[]
    for item in sorted(levels,key=lambda x:x['price']):
        if not out or abs(item['price']-out[-1]['mid'])>tolerance:
            out.append({'low':item['price'],'high':item['price'],'mid':item['price'],'touches':1,'sources':[item]})
        else:
            z=out[-1]; z['low']=min(z['low'],item['price']); z['high']=max(z['high'],item['price']); z['touches']+=1; z['sources'].append(item); z['mid']=(z['low']+z['high'])/2
    return out


def analyze_price_action(rows,timeframe):
    rows=list(rows or [])
    if len(rows)<60:
        return {'version':VERSION,'timeframe':timeframe,'ok':False,'reason':'INSUFFICIENT_CANDLES'}
    px=_f(rows[-1].get('close'))
    atr=_atr(rows,14)
    if px is None or atr is None or atr<=0:
        return {'version':VERSION,'timeframe':timeframe,'ok':False,'reason':'INVALID_PRICE_OR_ATR'}
    sample=rows[-160:]
    highs,lows=_swings(sample)
    tol=max(atr*0.35, px*0.0015)
    support_zones=_cluster_levels([{'price':x['price'],'kind':'SWING_LOW','time':x.get('time')} for x in lows],tol)
    resistance_zones=_cluster_levels([{'price':x['price'],'kind':'SWING_HIGH','time':x.get('time')} for x in highs],tol)
    support_zones=[z for z in support_zones if z['mid']<px]
    resistance_zones=[z for z in resistance_zones if z['mid']>px]
    support_zones.sort(key=lambda z:z['mid'],reverse=True); resistance_zones.sort(key=lambda z:z['mid'])
    nearest_support=support_zones[0] if support_zones else None
    nearest_resistance=resistance_zones[0] if resistance_zones else None

    prev_high=highs[-1]['price'] if highs else None
    prev_low=lows[-1]['price'] if lows else None
    c0=_f(rows[-1].get('close')); o0=_f(rows[-1].get('open')); h0=_f(rows[-1].get('high')); l0=_f(rows[-1].get('low'))
    c1=_f(rows[-2].get('close')) if len(rows)>1 else None
    bos='NONE'
    if prev_high is not None and c0>prev_high and (c1 is None or c1<=prev_high): bos='BOS_UP'
    elif prev_low is not None and c0<prev_low and (c1 is None or c1>=prev_low): bos='BOS_DOWN'

    sweep='NONE'
    if prev_high is not None and h0>prev_high and c0<prev_high: sweep='LIQUIDITY_SWEEP_HIGH'
    elif prev_low is not None and l0<prev_low and c0>prev_low: sweep='LIQUIDITY_SWEEP_LOW'

    rejection='NONE'
    body=max(abs(c0-o0),px*1e-9)
    upper=max(0,h0-max(c0,o0)); lower=max(0,min(c0,o0)-l0)
    if upper>=body*1.5 and nearest_resistance and h0>=nearest_resistance['low']-tol: rejection='BEARISH_REJECTION_AT_RESISTANCE'
    elif lower>=body*1.5 and nearest_support and l0<=nearest_support['high']+tol: rejection='BULLISH_REJECTION_AT_SUPPORT'

    retest='NONE'
    if prev_high is not None and c0>prev_high and l0<=prev_high+tol: retest='BULLISH_BREAKOUT_RETEST'
    elif prev_low is not None and c0<prev_low and h0>=prev_low-tol: retest='BEARISH_BREAKDOWN_RETEST'

    dist_support=((px-nearest_support['mid'])/px*100) if nearest_support else None
    dist_res=((nearest_resistance['mid']-px)/px*100) if nearest_resistance else None
    location='MID_RANGE'
    if dist_support is not None and dist_support<=0.6: location='NEAR_SUPPORT'
    if dist_res is not None and dist_res<=0.6: location='NEAR_RESISTANCE' if location=='MID_RANGE' else 'COMPRESSED_BETWEEN_LEVELS'

    scenario='RANGE_OR_TRANSITION'
    if bos=='BOS_UP' or retest=='BULLISH_BREAKOUT_RETEST': scenario='BULLISH_EXPANSION'
    elif bos=='BOS_DOWN' or retest=='BEARISH_BREAKDOWN_RETEST': scenario='BEARISH_EXPANSION'
    elif sweep=='LIQUIDITY_SWEEP_LOW' or rejection=='BULLISH_REJECTION_AT_SUPPORT': scenario='BULLISH_REVERSAL_WATCH'
    elif sweep=='LIQUIDITY_SWEEP_HIGH' or rejection=='BEARISH_REJECTION_AT_RESISTANCE': scenario='BEARISH_REVERSAL_WATCH'

    return {
        'version':VERSION,'timeframe':timeframe,'ok':True,'price':px,
        'break_of_structure':bos,'liquidity_sweep':sweep,'retest_state':retest,'rejection_state':rejection,
        'market_location':location,'scenario':scenario,
        'nearest_support_zone':nearest_support,'nearest_resistance_zone':nearest_resistance,
        'distance_to_support_pct':round(dist_support,4) if dist_support is not None else None,
        'distance_to_resistance_pct':round(dist_res,4) if dist_res is not None else None,
        'support_zone_count':len(support_zones),'resistance_zone_count':len(resistance_zones),
        'score_changed':False,'threshold_changed':False,'analysis_only':True,'live_execution':False,
    }


def combine_price_action(frame_states):
    pa4=(frame_states.get('4h') or {}).get('price_action') or {}
    pa12=(frame_states.get('12h') or {}).get('price_action') or {}
    s4=pa4.get('scenario'); s12=pa12.get('scenario')
    bullish={'BULLISH_EXPANSION','BULLISH_REVERSAL_WATCH'}
    bearish={'BEARISH_EXPANSION','BEARISH_REVERSAL_WATCH'}
    if s4 in bullish and s12 in bullish: state='BULLISH_CONFLUENCE'
    elif s4 in bearish and s12 in bearish: state='BEARISH_CONFLUENCE'
    elif (s4 in bullish and s12 in bearish) or (s4 in bearish and s12 in bullish): state='HTF_PRICE_ACTION_CONFLICT'
    else: state='NO_STRONG_PRICE_ACTION_CONFLUENCE'
    return {'version':VERSION,'status':state,'4h_scenario':s4,'12h_scenario':s12,'analysis_only':True,'live_execution':False}
