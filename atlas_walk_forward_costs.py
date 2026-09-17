#!/usr/bin/env python3
"""ATLAS Phase 4 walk-forward + transaction-cost evidence.
Research-only. Consumes paired Challenger evidence; never changes Production.
"""
from __future__ import annotations
import json, pathlib, os
ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'status/challenger-shadow-latest.json'
OUT=ROOT/'status/walk-forward-costs-latest.json'
SCHEMA='ATLAS_WALK_FORWARD_COSTS_V1'
FEE_BPS=float(os.getenv('ATLAS_RESEARCH_FEE_BPS','5'))
SLIPPAGE_BPS=float(os.getenv('ATLAS_RESEARCH_SLIPPAGE_BPS','3'))
FUNDING_BPS_12H=float(os.getenv('ATLAS_RESEARCH_FUNDING_BPS_12H','1'))
ROUND_TRIP_COST_PCT=(2*FEE_BPS+2*SLIPPAGE_BPS+FUNDING_BPS_12H)/100.0

def matured(r): return r.get('status')=='MATURED' and '12h' in (r.get('horizons') or {})
def enrich(r):
    x=dict(r); gross=float(r['horizons']['12h']['directional_return_pct']); net=gross-ROUND_TRIP_COST_PCT
    x['gross_12h_return_pct']=round(gross,6); x['assumed_round_trip_cost_pct']=round(ROUND_TRIP_COST_PCT,6); x['net_12h_return_pct']=round(net,6)
    x['research_only']=True; x['can_override_production']=False; x['live_execution']=False
    return x

def metrics(rows):
    if not rows: return {'n':0,'gross_expectancy_pct':None,'net_expectancy_pct':None,'win_rate_net_pct':None,'profit_factor_net':None,'max_drawdown_pct':None}
    gross=[r['gross_12h_return_pct'] for r in rows]; net=[r['net_12h_return_pct'] for r in rows]
    wins=sum(x>0 for x in net); gp=sum(x for x in net if x>0); gl=-sum(x for x in net if x<0)
    equity=0.0; peak=0.0; maxdd=0.0
    for x in net:
        equity+=x; peak=max(peak,equity); maxdd=max(maxdd,peak-equity)
    return {'n':len(rows),'gross_expectancy_pct':round(sum(gross)/len(gross),4),'net_expectancy_pct':round(sum(net)/len(net),4),'win_rate_net_pct':round(100*wins/len(net),2),'profit_factor_net':round(gp/gl,4) if gl>0 else None,'max_drawdown_pct':round(maxdd,4)}

def main():
    d=json.loads(SOURCE.read_text()); rows=[enrich(r) for r in d.get('records',[]) if matured(r)]
    by_direction={k:metrics([r for r in rows if r.get('shadow_action')==k]) for k in ('LONG','SHORT')}
    by_asset={s:metrics([r for r in rows if r.get('symbol')==s]) for s in sorted({r.get('symbol') for r in rows if r.get('symbol')})}
    report={'schema':SCHEMA,'source_schema':d.get('schema'),'comparison':'PAIRED_CHALLENGER_AFTER_EXPLICIT_COSTS','production_impact':'NONE','research_only':True,'can_override_production':False,'can_change_threshold':False,'production_threshold':68,'live_execution':False,'cost_assumptions':{'fee_bps_per_side':FEE_BPS,'slippage_bps_per_side':SLIPPAGE_BPS,'funding_bps_12h':FUNDING_BPS_12H,'round_trip_cost_pct':round(ROUND_TRIP_COST_PCT,6),'note':'Configurable research assumptions; not broker/exchange execution evidence.'},'summary':metrics(rows),'by_direction':by_direction,'by_asset':by_asset,'promotion_decision':'NOT_AUTHORIZED','records':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps({k:report[k] for k in ('schema','cost_assumptions','summary','by_direction')},indent=2))
if __name__=='__main__': main()
