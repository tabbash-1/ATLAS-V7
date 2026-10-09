"""ATLAS multi-asset 730-day profitability audit.
Research-only. Uses the frozen CORE 4-12H replay logic with unchanged threshold 68.
Evaluates BTC, ETH, SOL, XRP, DOGE and ZEC separately and by side at 10/20 bps.
No tuning; no Production effect.
"""
from __future__ import annotations
import json, statistics
from historical_core_4_12h_replay import fetch_1h, signal, settle

SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','ZECUSDT']
DAYS=730

def collect(symbol):
    rows=fetch_1h(symbol,DAYS); out=[]; i=720
    while i<len(rows)-12:
        s=signal(rows[:i+1])
        if not s['ready']:
            i+=4; continue
        r,o=settle(s,rows[i+1:i+13]); risk=abs(s['entry']-s['stop'])
        out.append({'t':rows[i]['t'],'side':s['side'],'entry':s['entry'],'risk_price':risk,'gross_r':r,'outcome':o})
        i+=12
    return sorted(out,key=lambda x:x['t'])

def stats(rows,bps):
    vals=[]
    for x in rows:
        cost=(bps/10000.0)*x['entry']/x['risk_price'] if x['risk_price'] else 0
        vals.append(x['gross_r']-cost)
    pos=[v for v in vals if v>0]; neg=[v for v in vals if v<=0]; gp=sum(pos); gl=abs(sum(neg))
    eq=10000.; peak=eq; dd=0
    for v in vals:
        eq*=1+0.01*v; peak=max(peak,eq); dd=max(dd,(peak-eq)/peak*100)
    return {
        'n':len(vals),'positive_pct':round(100*len(pos)/len(vals),2) if vals else 0,
        'avg_r':round(statistics.mean(vals),4) if vals else 0,'net_r':round(sum(vals),4),
        'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else 0),
        'max_dd_pct':round(dd,2),'net_return_pct':round((eq/10000-1)*100,2)
    }

def classify(s10,s20):
    pf10=s10['profit_factor'] if isinstance(s10['profit_factor'],float) else 99
    pf20=s20['profit_factor'] if isinstance(s20['profit_factor'],float) else 99
    if s10['net_r']>0 and pf10>=1.2 and s10['max_dd_pct']<=20 and s20['net_r']>0 and pf20>1:
        return 'PROMISING'
    if s10['net_r']>0 and pf10>1:
        return 'WEAK_EDGE'
    return 'NO_EDGE'

def main():
    out={'schema':'ATLAS_MULTI_ASSET_730D_PROFITABILITY_AUDIT_V1','days':DAYS,'research_only':True,'threshold_unchanged':68,'costs_bps':[10,20],'symbols':{}}
    for sym in SYMBOLS:
        tr=collect(sym); all10=stats(tr,10); all20=stats(tr,20)
        longs=[x for x in tr if x['side']=='LONG']; shorts=[x for x in tr if x['side']=='SHORT']
        out['symbols'][sym]={
            'overall_10bps':all10,'overall_20bps':all20,
            'long_10bps':stats(longs,10),'long_20bps':stats(longs,20),
            'short_10bps':stats(shorts,10),'short_20bps':stats(shorts,20),
            'classification':classify(all10,all20)
        }
    print('ATLAS_MULTI_ASSET_730D_AUDIT='+json.dumps(out,sort_keys=True))
if __name__=='__main__': main()
