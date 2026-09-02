#!/usr/bin/env python3
"""Scope offline path settlement without mislabeling shadow outcomes as realized P&L.

ATLAS live execution is disabled. Therefore no modelled/Execution-Ready path may
be called realized R. We retain two research cohorts while publishing an empty
realized summary until a real fill ledger exists.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'status/production-path-settlement-latest.json'
SCHEMA = 'ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V4_NO_FAKE_REALIZED_R'


def summarize(rows):
    terminal = [r for r in rows if r.get('terminal') and r.get('r_multiple') is not None]
    vals = [float(r['r_multiple']) for r in terminal]
    wins = [x for x in vals if x > 0]; losses = [x for x in vals if x < 0]
    pos, neg = sum(wins), abs(sum(losses))
    by_dir = {}
    for direction in ('LONG','SHORT'):
        dv = [float(r['r_multiple']) for r in terminal if (r.get('geometry') or {}).get('direction') == direction]
        by_dir[direction] = {'n':len(dv),'net_r':round(sum(dv),4),'avg_r':round(sum(dv)/len(dv),4) if dv else None,
                             'win_rate_pct':round(100*sum(x>0 for x in dv)/len(dv),2) if dv else None}
    providers = {}
    for r in rows:
        src=r.get('market_source')
        if src: providers[src]=providers.get(src,0)+1
    return {'episodes':len(rows),'terminal':len(terminal),'open_or_error':len(rows)-len(terminal),
            'wins':len(wins),'losses':len(losses),'win_rate_pct':round(100*len(wins)/len(terminal),2) if terminal else None,
            'net_r':round(sum(vals),4),'average_r':round(sum(vals)/len(vals),4) if vals else None,
            'profit_factor_r':round(pos/neg,4) if neg>0 else None,'by_direction':by_dir,
            'market_data_errors':sum(r.get('status')=='MARKET_DATA_ERROR' for r in rows),
            'ambiguous':sum(r.get('status')=='AMBIGUOUS' for r in rows),'provider_counts':providers}


def empty_realized_summary():
    return {'available':False,'reason':'LIVE_EXECUTION_DISABLED_NO_ACTUAL_FILL_LEDGER','episodes':0,'terminal':0,
            'open_or_error':0,'wins':0,'losses':0,'win_rate_pct':None,'net_r':None,'average_r':None,
            'profit_factor_r':None,'by_direction':{'LONG':{'n':0,'net_r':None,'avg_r':None,'win_rate_pct':None},
            'SHORT':{'n':0,'net_r':None,'avg_r':None,'win_rate_pct':None}},'market_data_errors':0,'ambiguous':0,'provider_counts':{}}


def main():
    raw=json.loads(PATH.read_text())
    records=list(raw.get('records') or [])
    executable=[r for r in records if r.get('execution_ready_at_capture') is True]
    conditional=[r for r in records if r.get('execution_ready_at_capture') is not True]
    raw['upstream_schema']=raw.get('schema')
    raw['schema']=SCHEMA
    raw['scoped_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    raw['scope_semantics']={
        'plan_shadow':'ALL_PRODUCTION_QUALIFIED_CANONICAL_PLANS; RESEARCH ONLY',
        'execution_ready_shadow':'PRODUCTION_QUALIFIED AND execution_ready_at_capture=true; MODELLED PATH, NOT A FILL',
        'realized_r_authority':'ACTUAL_LIVE_FILL_LEDGER_ONLY',
    }
    raw['plan_shadow_summary']=summarize(records)
    raw['execution_ready_shadow_summary']=summarize(executable)
    raw['conditional_not_executed_summary']=summarize(conditional)
    raw.pop('execution_ready_summary',None)
    raw['summary']=empty_realized_summary()
    raw['realized_r_scope']='ACTUAL_LIVE_FILL_LEDGER_ONLY'
    raw['realized_r_available']=False
    raw['execution_ready_shadow_is_realized_r']=False
    raw['plan_shadow_is_realized_r']=False
    raw['research_only']=True
    raw['live_execution']=False
    raw['can_override_production']=False
    raw['can_change_threshold']=False
    raw['production_threshold_unchanged']=68
    PATH.write_text(json.dumps(raw,indent=2,sort_keys=True))
    print(json.dumps({'schema':raw['schema'],'realized':raw['summary'],
                      'execution_ready_shadow':raw['execution_ready_shadow_summary'],
                      'plan_shadow':raw['plan_shadow_summary']},indent=2))

if __name__=='__main__': main()
