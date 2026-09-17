#!/usr/bin/env python3
"""ATLAS Phase 4 walk-forward + explicit-cost robustness evidence.
Research-only. Consumes paired Challenger evidence; never changes Production.
"""
from __future__ import annotations
import json, pathlib, os
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'status/challenger-shadow-latest.json'
OUT=ROOT/'status/walk-forward-costs-latest.json'
SCHEMA='ATLAS_WALK_FORWARD_COSTS_V2_COMPLETE'
FEE_BPS=float(os.getenv('ATLAS_RESEARCH_FEE_BPS','5'))
SLIPPAGE_BPS=float(os.getenv('ATLAS_RESEARCH_SLIPPAGE_BPS','3'))
FUNDING_BPS_12H=float(os.getenv('ATLAS_RESEARCH_FUNDING_BPS_12H','1'))
HOURS=(4,8,12)

def cost_pct(hours=12, multiplier=1.0):
    funding=FUNDING_BPS_12H*(hours/12.0)
    return multiplier*(2*FEE_BPS+2*SLIPPAGE_BPS+funding)/100.0

def matured(r,h=12): return r.get('status')=='MATURED' and f'{h}h' in (r.get('horizons') or {})
def enrich(r):
    x=dict(r); x['research_only']=True; x['can_override_production']=False; x['live_execution']=False
    for h in HOURS:
        if f'{h}h' in (r.get('horizons') or {}):
            gross=float(r['horizons'][f'{h}h']['directional_return_pct']); c=cost_pct(h)
            x[f'gross_{h}h_return_pct']=round(gross,6); x[f'assumed_{h}h_cost_pct']=round(c,6); x[f'net_{h}h_return_pct']=round(gross-c,6)
    return x

def metrics(rows,h=12,cost_multiplier=1.0):
    vals=[]; gross=[]
    for r in rows:
        if not matured(r,h): continue
        g=float(r['horizons'][f'{h}h']['directional_return_pct']); gross.append(g); vals.append(g-cost_pct(h,cost_multiplier))
    if not vals: return {'n':0,'gross_expectancy_pct':None,'net_expectancy_pct':None,'win_rate_net_pct':None,'profit_factor_net':None,'max_drawdown_pct':None}
    wins=sum(x>0 for x in vals); gp=sum(x for x in vals if x>0); gl=-sum(x for x in vals if x<0)
    equity=peak=maxdd=0.0
    for x in vals:
        equity+=x; peak=max(peak,equity); maxdd=max(maxdd,peak-equity)
    return {'n':len(vals),'gross_expectancy_pct':round(sum(gross)/len(gross),4),'net_expectancy_pct':round(sum(vals)/len(vals),4),'win_rate_net_pct':round(100*wins/len(vals),2),'profit_factor_net':round(gp/gl,4) if gl>0 else None,'max_drawdown_pct':round(maxdd,4)}

def main():
    d=json.loads(SOURCE.read_text()); base=[r for r in d.get('records',[]) if matured(r,12)]; rows=[enrich(r) for r in base]
    horizon_metrics={f'{h}h':metrics(base,h) for h in HOURS}
    by_direction={k:{f'{h}h':metrics([r for r in base if r.get('shadow_action')==k],h) for h in HOURS} for k in ('LONG','SHORT')}
    by_asset={s:{f'{h}h':metrics([r for r in base if r.get('symbol')==s],h) for h in HOURS} for s in sorted({r.get('symbol') for r in base if r.get('symbol')})}
    stress={'zero_cost_12h':metrics(base,12,0.0),'base_cost_12h':metrics(base,12,1.0),'double_cost_12h':metrics(base,12,2.0)}
    report={'schema':SCHEMA,'source_schema':d.get('schema'),'comparison':'PAIRED_CHALLENGER_MULTI_HORIZON_AFTER_EXPLICIT_COSTS','production_impact':'NONE','research_only':True,'can_override_production':False,'can_change_threshold':False,'production_threshold':68,'live_execution':False,'cost_assumptions':{'fee_bps_per_side':FEE_BPS,'slippage_bps_per_side':SLIPPAGE_BPS,'funding_bps_12h':FUNDING_BPS_12H,'cost_4h_pct':round(cost_pct(4),6),'cost_8h_pct':round(cost_pct(8),6),'cost_12h_pct':round(cost_pct(12),6),'note':'Configurable research assumptions; not broker/exchange execution evidence.'},'summary':horizon_metrics['12h'],'horizon_metrics':horizon_metrics,'by_direction':by_direction,'by_asset':by_asset,'cost_stress':stress,'sample_review_ready':len(base)>=30,'robustness_gate':{'requires_positive_net_expectancy':True,'requires_profit_factor_gt_1':True,'requires_positive_under_double_costs':True,'passed':bool(stress['base_cost_12h']['net_expectancy_pct'] and stress['base_cost_12h']['net_expectancy_pct']>0 and stress['base_cost_12h']['profit_factor_net'] and stress['base_cost_12h']['profit_factor_net']>1 and stress['double_cost_12h']['net_expectancy_pct'] and stress['double_cost_12h']['net_expectancy_pct']>0)},'promotion_decision':'NOT_AUTHORIZED','records':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps({k:report[k] for k in ('schema','cost_assumptions','horizon_metrics','by_direction','cost_stress','robustness_gate')},indent=2))
if __name__=='__main__': main()
