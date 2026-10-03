"""ATLAS indicator attribution audit.
Research only. Measures which frozen signal components are associated with better
12h outcomes. It does not change Production or optimize thresholds.
"""
from __future__ import annotations
import json, statistics
from historical_core_4_12h_replay import fetch_1h,resample,direction,rsi,atr,settle

SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','ZECUSDT']
DAYS=730
COST_BPS=10

def pf(vals):
 p=sum(x for x in vals if x>0); n=abs(sum(x for x in vals if x<=0))
 return round(p/n,4) if n else ('INF' if p else 0)

def stats(rows):
 vals=[x['net_r'] for x in rows]
 return {'n':len(vals),'positive_pct':round(100*sum(x>0 for x in vals)/len(vals),2) if vals else 0,'avg_r':round(statistics.mean(vals),4) if vals else 0,'net_r':round(sum(vals),4),'profit_factor':pf(vals)}

def cost_r(entry,risk): return (COST_BPS/10000.0)*entry/risk if risk else 0

def build(symbol):
 rows=fetch_1h(symbol,DAYS); out=[]; i=720
 while i<len(rows)-12:
  hist=rows[:i+1]; r4=resample(hist,4); r12=resample(hist,12)
  d4=direction(r4); d12=direction(r12); d1=direction(hist)
  if not d4 or d4!=d12: i+=4; continue
  side=d4; a=atr(hist)
  if not a: i+=4; continue
  entry=hist[-1]['c']; stop=entry-1.5*a if side=='LONG' else entry+1.5*a; target=entry+3*a if side=='LONG' else entry-3*a
  sig={'side':side,'entry':entry,'stop':stop,'target':target}; gross,outcome=settle(sig,rows[i+1:i+13]); risk=abs(entry-stop)
  rs=rsi([x['c'] for x in hist]); recent4=r4[-8:]
  f_1h=(d1==side)
  f_rsi=(rs is not None and ((side=='LONG' and 52<=rs<=75) or (side=='SHORT' and 25<=rs<=48)))
  f_structure=((side=='LONG' and recent4[-1]['c']>max(x['h'] for x in recent4[-4:-1])) or (side=='SHORT' and recent4[-1]['c']<min(x['l'] for x in recent4[-4:-1])))
  vols=[x['v'] for x in hist[-25:-1]]; f_volume=bool(vols and hist[-1]['v']>=statistics.mean(vols))
  score=40+15*sum((f_1h,f_rsi,f_structure,f_volume))
  out.append({'symbol':symbol,'side':side,'score':score,'f_1h':f_1h,'f_rsi':f_rsi,'f_structure':f_structure,'f_volume':f_volume,'gross_r':gross,'net_r':gross-cost_r(entry,risk),'outcome':outcome})
  i+=4
 return out

def compare(rows,key):
 on=[x for x in rows if x[key]]; off=[x for x in rows if not x[key]]
 a,b=stats(on),stats(off)
 return {'on':a,'off':b,'uplift_avg_r':round(a['avg_r']-b['avg_r'],4),'uplift_positive_pct':round(a['positive_pct']-b['positive_pct'],2)}

def combos(rows):
 keys=['f_1h','f_rsi','f_structure','f_volume']; out=[]
 for mask in range(1,16):
  ks=[keys[j] for j in range(4) if mask&(1<<j)]
  subset=[x for x in rows if all(x[k] for k in ks)]
  if len(subset)>=30: out.append({'factors':ks,**stats(subset)})
 return sorted(out,key=lambda x:(x['avg_r'],x['profit_factor'] if isinstance(x['profit_factor'],float) else 99),reverse=True)

def report(rows):
 return {'all_htf_aligned':stats(rows),'factors':{k:compare(rows,k) for k in ['f_1h','f_rsi','f_structure','f_volume']},'top_combinations_min_n30':combos(rows)[:10]}

def main():
 allrows=[]; by={}
 for s in SYMBOLS:
  r=build(s); allrows+=r; by[s]=report(r)
 focus=[x for x in allrows if x['symbol']=='XRPUSDT' and x['side']=='LONG']
 result={'schema':'ATLAS_INDICATOR_ATTRIBUTION_AUDIT_V1','research_only':True,'days':DAYS,'cost_bps':COST_BPS,'important_note':'Association/conditional uplift, not causal proof; factors are correlated. HTF 4H/12H alignment is the sampling prerequisite and therefore cannot be compared on/off in this audit.','by_symbol':by,'xrp_long_focus':report(focus),'all_symbols':report(allrows)}
 print('ATLAS_INDICATOR_ATTRIBUTION='+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
