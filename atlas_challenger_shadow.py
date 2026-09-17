#!/usr/bin/env python3
"""ATLAS Phase 3 paired Champion/Challenger evidence engine.

Research-only. Champion remains canonical WAIT. Challenger records the captured
LONG/SHORT candidate as a shadow action only for the narrow post-V2 neutral-regime
HTF-conflict hypothesis. No Production, threshold, risk, SL/TP or execution change.
"""
from __future__ import annotations
import json, pathlib

ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/'status/wait-missed-opportunity-latest.json'
OUT=ROOT/'status/challenger-shadow-latest.json'
SCHEMA='ATLAS_CHALLENGER_SHADOW_V2_PAIRED_EVIDENCE'
MIN_MATURED_FOR_PROMOTION_REVIEW=30


def eligible(r):
    return (r.get('epoch_id')=='HTF_SR_V2_2026-09-14' and
            r.get('v2_regime')=='4H_DIRECTIONAL_12H_NEUTRAL' and
            r.get('blocker_family')=='HTF_CONFLICT' and
            r.get('direction') in {'LONG','SHORT'})


def mature12(r):
    return r.get('status')=='MATURED' and '12h' in (r.get('horizons') or {})


def paired(r):
    x=dict(r)
    x['canonical_action']='WAIT'
    x['shadow_action']=r.get('direction') if eligible(r) else 'WAIT'
    x['shadow_reason']='RESEARCH_4H_DIRECTIONAL_12H_NEUTRAL_HTF_CONFLICT' if eligible(r) else None
    x['research_only']=True; x['can_override_production']=False; x['live_execution']=False
    return x


def metrics(rows):
    matured=[r for r in rows if mature12(r)]
    def vals(h,field): return [r['horizons'][h][field] for r in matured if h in (r.get('horizons') or {}) and r['horizons'][h].get(field) is not None]
    def mean(h,field):
        v=vals(h,field); return round(sum(v)/len(v),4) if v else None
    def positive(h):
        v=vals(h,'directional_return_pct'); return round(100*sum(x>0 for x in v)/len(v),2) if v else None
    out={'eligible_records':len(rows),'matured_12h':len(matured),'canonical_action':'WAIT','shadow_actions':{'LONG':sum(r.get('direction')=='LONG' for r in rows),'SHORT':sum(r.get('direction')=='SHORT' for r in rows)}}
    for h in ('4h','8h','12h'):
        out[f'mean_{h}_directional_return_pct']=mean(h,'directional_return_pct')
        out[f'positive_{h}_rate_pct']=positive(h)
    out['mean_12h_mfe_pct']=mean('12h','mfe_pct'); out['mean_12h_mae_pct']=mean('12h','mae_pct')
    out['missed_opportunity_n']=sum(bool(r.get('missed_opportunity')) for r in matured)
    out['invalidation_12h_n']=sum(bool(r['horizons']['12h'].get('invalidation_hit')) for r in matured)
    out['by_direction']={}
    for d in ('LONG','SHORT'):
        rs=[r for r in matured if r.get('direction')==d]
        v=[r['horizons']['12h']['directional_return_pct'] for r in rs]
        out['by_direction'][d]={'n':len(rs),'mean_12h_directional_return_pct':round(sum(v)/len(v),4) if v else None,'positive_12h_rate_pct':round(100*sum(x>0 for x in v)/len(v),2) if v else None,'missed_n':sum(bool(r.get('missed_opportunity')) for r in rs),'invalidation_n':sum(bool(r['horizons']['12h'].get('invalidation_hit')) for r in rs)}
    return out


def main():
    data=json.loads(SOURCE.read_text())
    rows=[paired(r) for r in data.get('records',[]) if eligible(r)]
    s=metrics(rows); enough=s['matured_12h']>=MIN_MATURED_FOR_PROMOTION_REVIEW
    report={'schema':SCHEMA,'source_schema':data.get('schema'),'generated_from':str(SOURCE.relative_to(ROOT)),'comparison':'CANONICAL_WAIT_VS_CAPTURED_DIRECTION_SHADOW','hypothesis':'Treat 12H neutral as distinct from explicit opposition only in shadow; test whether captured 4H directional bias has forward edge.','production_impact':'NONE','research_only':True,'can_override_production':False,'can_change_threshold':False,'production_threshold':68,'live_execution':False,'minimum_matured_for_promotion_review':MIN_MATURED_FOR_PROMOTION_REVIEW,'promotion_review_sample_ready':enough,'promotion_decision':'NOT_AUTHORIZED','summary':s,'records':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({'schema':SCHEMA,'summary':s,'promotion_review_sample_ready':enough},indent=2))

if __name__=='__main__': main()
