#!/usr/bin/env python3
"""ATLAS Phase 3 Challenger Shadow Engine.

Research-only comparator. It never mutates Production decisions, score, threshold,
risk, SL/TP or execution. The first challenger hypothesis is deliberately narrow:
measure WAIT decisions in the 4H_DIRECTIONAL_12H_NEUTRAL regime where HTF is the
primary blocker, while preserving every other production gate as evidence.
"""
from __future__ import annotations
import json
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / 'status/wait-missed-opportunity-latest.json'
OUT = ROOT / 'status/challenger-shadow-latest.json'
SCHEMA = 'ATLAS_CHALLENGER_SHADOW_V1'
MIN_MATURED_FOR_PROMOTION_REVIEW = 30


def eligible(r):
    return (
        r.get('epoch_id') == 'HTF_SR_V2_2026-09-14'
        and r.get('v2_regime') == '4H_DIRECTIONAL_12H_NEUTRAL'
        and r.get('blocker_family') == 'HTF_CONFLICT'
        and r.get('direction') in {'LONG','SHORT'}
    )


def summarize(rows):
    matured=[r for r in rows if r.get('status')=='MATURED' and '12h' in (r.get('horizons') or {})]
    def mean(field,h):
        vals=[r['horizons'][h][field] for r in matured if h in (r.get('horizons') or {})]
        return round(sum(vals)/len(vals),4) if vals else None
    by_direction={}
    for direction in ('LONG','SHORT'):
        rs=[r for r in matured if r.get('direction')==direction]
        by_direction[direction]={'n':len(rs),'mean_12h_directional_return_pct':round(sum(r['horizons']['12h']['directional_return_pct'] for r in rs)/len(rs),4) if rs else None,'missed_n':sum(bool(r.get('missed_opportunity')) for r in rs)}
    return {
        'eligible_records':len(rows),
        'matured_12h':len(matured),
        'mean_4h_directional_return_pct':mean('directional_return_pct','4h'),
        'mean_8h_directional_return_pct':mean('directional_return_pct','8h'),
        'mean_12h_directional_return_pct':mean('directional_return_pct','12h'),
        'mean_12h_mfe_pct':mean('mfe_pct','12h'),
        'mean_12h_mae_pct':mean('mae_pct','12h'),
        'missed_opportunity_n':sum(bool(r.get('missed_opportunity')) for r in matured),
        'by_direction':by_direction,
    }


def main():
    data=json.loads(SOURCE.read_text())
    rows=[r for r in data.get('records',[]) if eligible(r)]
    s=summarize(rows)
    enough=s['matured_12h'] >= MIN_MATURED_FOR_PROMOTION_REVIEW
    report={
        'schema':SCHEMA,
        'source_schema':data.get('schema'),
        'generated_from':str(SOURCE.relative_to(ROOT)),
        'hypothesis':'Treat 12H neutral as distinct from explicit opposition only in shadow; measure whether 4H directional candidate bias has forward edge.',
        'production_impact':'NONE',
        'research_only':True,
        'can_override_production':False,
        'can_change_threshold':False,
        'production_threshold':68,
        'live_execution':False,
        'minimum_matured_for_promotion_review':MIN_MATURED_FOR_PROMOTION_REVIEW,
        'promotion_review_sample_ready':enough,
        'promotion_decision':'NOT_AUTHORIZED',
        'summary':s,
        'records':rows,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({'schema':SCHEMA,'summary':s,'promotion_review_sample_ready':enough},indent=2))

if __name__=='__main__': main()
