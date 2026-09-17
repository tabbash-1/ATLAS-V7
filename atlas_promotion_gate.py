#!/usr/bin/env python3
"""ATLAS Phase 5 Promotion Gate.
Research-only evidence review. It can recommend further review, never mutate Production.
Criteria are fixed ex ante and intentionally conservative.
"""
from __future__ import annotations
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'status/walk-forward-costs-latest.json'
OUT=ROOT/'status/promotion-gate-latest.json'
SCHEMA='ATLAS_PROMOTION_GATE_V1'
MIN_N=30
MIN_PF=1.10
MAX_DD_PCT=20.0
MIN_SEGMENT_N=10


def metric_pass(m):
    return bool(m and m.get('n',0)>=MIN_N and m.get('net_expectancy_pct') is not None and m['net_expectancy_pct']>0 and m.get('profit_factor_net') is not None and m['profit_factor_net']>=MIN_PF and m.get('max_drawdown_pct') is not None and m['max_drawdown_pct']<=MAX_DD_PCT)

def row_net(r,h=12):
    v=r.get(f'net_{h}h_return_pct')
    return None if v is None else float(v)

def segment_metrics(rows,h=12):
    vals=[row_net(r,h) for r in rows if row_net(r,h) is not None]
    if not vals: return {'n':0,'net_expectancy_pct':None,'positive_rate_pct':None}
    return {'n':len(vals),'net_expectancy_pct':round(sum(vals)/len(vals),4),'positive_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),2)}

def chronological_robustness(rows,h=12):
    rs=[r for r in rows if row_net(r,h) is not None]
    rs=sorted(rs,key=lambda r:str(r.get('captured_at') or r.get('decision_id') or ''))
    cut=len(rs)//2; early=segment_metrics(rs[:cut],h); late=segment_metrics(rs[cut:],h)
    passed=early['n']>=MIN_SEGMENT_N and late['n']>=MIN_SEGMENT_N and early['net_expectancy_pct']>0 and late['net_expectancy_pct']>0
    return {'early':early,'late':late,'requires_each_segment_n':MIN_SEGMENT_N,'requires_positive_expectancy_each_segment':True,'passed':passed}

def evaluate(name,m,rows,double_cost_net=None):
    sample=m.get('n',0)>=MIN_N
    expectancy=m.get('net_expectancy_pct') is not None and m['net_expectancy_pct']>0
    pf=m.get('profit_factor_net') is not None and m['profit_factor_net']>=MIN_PF
    dd=m.get('max_drawdown_pct') is not None and m['max_drawdown_pct']<=MAX_DD_PCT
    stress=double_cost_net is not None and double_cost_net>0
    chrono=chronological_robustness(rows,12)
    passed=sample and expectancy and pf and dd and stress and chrono['passed']
    return {'cohort':name,'criteria':{'minimum_n':MIN_N,'minimum_profit_factor':MIN_PF,'maximum_drawdown_pct':MAX_DD_PCT,'positive_net_expectancy':True,'positive_double_cost_expectancy':True,'chronological_split_positive':True},'observed':m,'double_cost_net_expectancy_pct':double_cost_net,'chronological_split':chrono,'gates':{'sample':sample,'net_expectancy':expectancy,'profit_factor':pf,'drawdown':dd,'double_cost_stress':stress,'chronological_robustness':chrono['passed']},'passed':passed}

def main():
    d=json.loads(SOURCE.read_text()); rows=d.get('records',[])
    overall=d['horizon_metrics']['12h']; double=d['cost_stress']['double_cost_12h']['net_expectancy_pct']
    evaluations=[evaluate('BROAD_12H',overall,rows,double)]
    # Diagnostics only: pre-specified direction cohorts. Same >=30 rule; no subgroup can bypass sample/robustness gates.
    for direction in ('LONG','SHORT'):
        m=d.get('by_direction',{}).get(direction,{}).get('12h',{})
        sub=[r for r in rows if r.get('shadow_action')==direction]
        # derive double-cost diagnostic from base net by subtracting one additional base cost
        extra=float(d['cost_assumptions']['cost_12h_pct']); dn=None if m.get('net_expectancy_pct') is None else round(m['net_expectancy_pct']-extra,4)
        evaluations.append(evaluate(f'{direction}_12H',m,sub,dn))
    passed=[e['cohort'] for e in evaluations if e['passed']]
    decision='ELIGIBLE_FOR_MANUAL_PRODUCTION_REVIEW' if passed else 'NO_PROMOTION'
    report={'schema':SCHEMA,'phase':'5_OF_6','source_schema':d.get('schema'),'criteria_locked_before_evaluation':True,'production_impact':'NONE','research_only':True,'can_override_production':False,'can_change_threshold':False,'production_threshold':68,'live_execution':False,'automatic_promotion':False,'promotion_decision':decision,'passing_cohorts':passed,'evaluations':evaluations,'policy':'Passing only authorizes manual Phase 6 review. It never changes Production automatically; failing evidence preserves current Production.'}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
