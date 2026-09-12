"""ATLAS ZEC profitability audit.
Research-only wrapper around the frozen CORE 4-12H historical replay.
Does not alter Production or thresholds. Adds chronological, side, regime and
round-trip cost sensitivity needed to answer whether the thesis is profitable.
"""
from __future__ import annotations
import argparse, json, statistics
from historical_core_4_12h_replay import fetch_1h, signal, settle

VERSION="ATLAS_ZEC_PROFITABILITY_AUDIT_V1"

def regime(hist):
    # Past-only 1D proxy from 1H closes: 20d vs 50d SMA and current vs 20d.
    closes=[x['c'] for x in hist]
    if len(closes)<24*50:return 'UNKNOWN'
    s20=statistics.mean(closes[-24*20:]); s50=statistics.mean(closes[-24*50:]); c=closes[-1]
    if c>s20>s50:return 'BULL'
    if c<s20<s50:return 'BEAR'
    return 'RANGE_TRANSITION'

def collect(days):
    rows=fetch_1h('ZECUSDT',days); warm=60*12; out=[]; i=warm
    while i<len(rows)-12:
        s=signal(rows[:i+1])
        if not s['ready']: i+=4; continue
        r,o=settle(s,rows[i+1:i+13]); risk=abs(s['entry']-s['stop'])
        out.append({'t':rows[i]['t'],'side':s['side'],'score':s['score'],'entry':s['entry'],'risk_price':risk,'gross_r':r,'outcome':o,'regime':regime(rows[:i+1])})
        i+=12
    return out

def stats(rows,cost_bps=0):
    vals=[]
    for x in rows:
        # round-trip trading friction as fraction of notional converted to R.
        cost_r=(cost_bps/10000.0)*x['entry']/x['risk_price'] if x['risk_price'] else 0
        vals.append(x['gross_r']-cost_r)
    pos=[v for v in vals if v>0]; neg=[v for v in vals if v<=0]; gp=sum(pos); gl=abs(sum(neg))
    eq=10000.;peak=eq;dd=0
    for v in vals:
        eq*=1+0.01*v;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak*100)
    return {'n':len(vals),'positive_pct':round(100*len(pos)/len(vals),2) if vals else 0,'avg_r':round(statistics.mean(vals),4) if vals else 0,'net_r':round(sum(vals),4),'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else 0),'max_dd_pct':round(dd,2),'equity_1pct_risk':round(eq,2),'net_return_pct':round((eq/10000-1)*100,2)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--days',type=int,default=365);a=ap.parse_args();tr=collect(a.days)
    costs={str(b):stats(tr,b) for b in (0,5,10,20)}
    sides={s:{str(b):stats([x for x in tr if x['side']==s],b) for b in (0,10)} for s in ('LONG','SHORT')}
    regimes={r:{str(b):stats([x for x in tr if x['regime']==r],b) for b in (0,10)} for r in ('BULL','BEAR','RANGE_TRANSITION')}
    result={'schema':VERSION,'research_only':True,'symbol':'ZECUSDT','days':a.days,'threshold_unchanged':68,'cost_bps_round_trip_sensitivity':[0,5,10,20],'cost_note':'Cost sensitivity is an assumption, not observed venue-specific execution cost. Funding excluded.','overall_by_cost_bps':costs,'by_side':sides,'by_regime':regimes,'trades':len(tr),'verdict_at_10bps':'PROFITABLE' if costs['10']['net_r']>0 and isinstance(costs['10']['profit_factor'],float) and costs['10']['profit_factor']>1 else 'NOT_PROFITABLE'}
    print('ATLAS_ZEC_PROFITABILITY_AUDIT='+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
