#!/usr/bin/env python3
"""ATLAS Phase 5 Promotion Gate. Evidence governance only; cannot alter Production."""
from __future__ import annotations
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'status/walk-forward-costs-latest.json'
OUT=ROOT/'status/promotion-gate-latest.json'
SCHEMA='ATLAS_PROMOTION_GATE_V1'
MIN_MATURED=30
MIN_NET_EXPECTANCY_PCT=0.0
MIN_PROFIT_FACTOR=1.0
MAX_DRAWDOWN_PCT=20.0
MIN_WIN_RATE_PCT=50.0

def evaluate_bucket(name,m,stress=None):
    n=int(m.get('n') or 0); ne=m.get('net_expectancy_pct'); pf=m.get('profit_factor_net'); dd=m.get('max_drawdown_pct'); wr=m.get('win_rate_net_pct')
    checks={
      'sample_size': n>=MIN_MATURED,
      'positive_net_expectancy': ne is not None and ne>MIN_NET_EXPECTANCY_PCT,
      'profit_factor_gt_1': pf is not None and pf>MIN_PROFIT_FACTOR,
      'drawdown_lte_20pct': dd is not None and dd<=MAX_DRAWDOWN_PCT,
      'win_rate_gte_50pct': wr is not None and wr>=MIN_WIN_RATE_PCT,
    }
    if stress is not None:
      s=stress.get('double_cost_12h') or {}; checks['double_cost_positive']=s.get('net_expectancy_pct') is not None and s['net_expectancy_pct']>0
    passed=all(checks.values())
    return {'name':name,'metrics':m,'checks':checks,'evidence_passed':passed,'production_authorization':'NOT_AUTHORIZED'}

def main():
    d=json.loads(SOURCE.read_text())
    candidates=[]
    for h,m in d.get('horizon_metrics',{}).items(): candidates.append(evaluate_bucket(f'ALL_{h.upper()}',m,d.get('cost_stress') if h=='12h' else None))
    for direction,hm in d.get('by_direction',{}).items():
      for h,m in hm.items(): candidates.append(evaluate_bucket(f'{direction}_{h.upper()}',m))
    evidence_pass=[c for c in candidates if c['evidence_passed']]
    report={'schema':SCHEMA,'source_schema':d.get('schema'),'phase':'5_OF_6','purpose':'EVIDENCE_GOVERNANCE_NOT_STRATEGY_OPTIMIZATION','production_impact':'NONE','research_only':True,'can_override_production':False,'can_change_threshold':False,'production_threshold':68,'live_execution':False,'criteria':{'min_matured':MIN_MATURED,'net_expectancy_pct_gt':MIN_NET_EXPECTANCY_PCT,'profit_factor_gt':MIN_PROFIT_FACTOR,'max_drawdown_pct_lte':MAX_DRAWDOWN_PCT,'win_rate_pct_gte':MIN_WIN_RATE_PCT,'note':'Criteria are governance gates, not tuning targets. Passing evidence never auto-promotes.'},'candidates':candidates,'evidence_passed_candidates':[c['name'] for c in evidence_pass],'promotion_decision':'NOT_AUTHORIZED','promotion_reason':'NO_AUTOMATIC_PROMOTION; separate reviewed Production change and new epoch required even if evidence passes.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps({'schema':SCHEMA,'evidence_passed_candidates':report['evidence_passed_candidates'],'promotion_decision':report['promotion_decision']},indent=2))
if __name__=='__main__': main()
