"""ATLAS ZEC profitability audit V2.
Research-only. Production and threshold remain untouched. Tests the frozen CORE
4-12H thesis, costs, sides/regimes, plus chronological walk-forward validation
of the predeclared ZEC LONG candidate. No tuning is performed on test folds.
"""
from __future__ import annotations
import argparse,json,statistics
from historical_core_4_12h_replay import fetch_1h,signal,settle
VERSION='ATLAS_ZEC_PROFITABILITY_AUDIT_V2'

def regime(hist):
 c=[x['c'] for x in hist]
 if len(c)<1200:return 'UNKNOWN'
 s20=statistics.mean(c[-480:]);s50=statistics.mean(c[-1200:]);x=c[-1]
 if x>s20>s50:return 'BULL'
 if x<s20<s50:return 'BEAR'
 return 'RANGE_TRANSITION'

def collect(days):
 rows=fetch_1h('ZECUSDT',days);out=[];i=720
 while i<len(rows)-12:
  s=signal(rows[:i+1])
  if not s['ready']:i+=4;continue
  r,o=settle(s,rows[i+1:i+13]);risk=abs(s['entry']-s['stop'])
  out.append({'t':rows[i]['t'],'side':s['side'],'score':s['score'],'entry':s['entry'],'risk_price':risk,'gross_r':r,'outcome':o,'regime':regime(rows[:i+1])});i+=12
 return sorted(out,key=lambda x:x['t'])

def netr(x,bps):return x['gross_r']-(bps/10000)*x['entry']/x['risk_price']
def stats(rows,bps=10):
 v=[netr(x,bps) for x in rows];p=[x for x in v if x>0];n=[x for x in v if x<=0];gp=sum(p);gl=abs(sum(n));eq=10000.;peak=eq;dd=0
 for x in v:eq*=1+.01*x;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak*100)
 return {'n':len(v),'positive_pct':round(100*len(p)/len(v),2) if v else 0,'avg_r':round(statistics.mean(v),4) if v else 0,'net_r':round(sum(v),4),'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else 0),'max_dd_pct':round(dd,2),'net_return_pct':round((eq/10000-1)*100,2)}

def walk_forward(long_rows,bps=10):
 # Candidate was declared before this validation: ZEC LONG, unchanged score/geometry.
 # Four chronological folds; each fold is reported independently. No fold changes rules.
 n=len(long_rows);folds=[]
 for k in range(4):
  a=k*n//4;b=(k+1)*n//4;part=long_rows[a:b];folds.append({'fold':k+1,'start_ms':part[0]['t'] if part else None,'end_ms':part[-1]['t'] if part else None,**stats(part,bps)})
 profitable=sum(1 for f in folds if f['net_r']>0 and isinstance(f['profit_factor'],float) and f['profit_factor']>1)
 return {'method':'CHRONOLOGICAL_4_FOLD_FROZEN_RULES','cost_bps':bps,'candidate':'ZEC_LONG_CORE_4_12H_THRESHOLD_68','no_parameter_tuning_between_folds':True,'folds':folds,'profitable_folds':profitable,'robustness_verdict':'ROBUST_4_OF_4' if profitable==4 else ('PARTIAL' if profitable>=3 else 'NOT_ROBUST')}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--days',type=int,default=365);a=ap.parse_args();tr=collect(a.days);longs=[x for x in tr if x['side']=='LONG'];shorts=[x for x in tr if x['side']=='SHORT']
 result={'schema':VERSION,'research_only':True,'forward_proof_equivalent':False,'symbol':'ZECUSDT','days':a.days,'threshold_unchanged':68,'overall_by_cost_bps':{str(b):stats(tr,b) for b in (0,5,10,20)},'by_side':{'LONG':stats(longs,10),'SHORT':stats(shorts,10)},'long_by_regime':{r:stats([x for x in longs if x['regime']==r],10) for r in ('BULL','BEAR','RANGE_TRANSITION')},'walk_forward_long':walk_forward(longs,10),'cost_note':'10 bps is an assumed round-trip friction; funding excluded.','decision_rule':'Do not promote from retrospective evidence alone; require forward paper evidence.'}
 print('ATLAS_ZEC_PROFITABILITY_AUDIT='+json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
