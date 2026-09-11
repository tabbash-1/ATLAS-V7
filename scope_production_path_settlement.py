#!/usr/bin/env python3
"""Scope offline path settlement without mislabeling shadow outcomes as realized P&L.

ATLAS live execution is disabled. Therefore no modelled/Execution-Ready path may
be called realized R. We retain research cohorts while publishing an empty
realized summary until a real fill ledger exists.

The historical SHORT score sweep is counterfactual research only. It reuses the
already-settled canonical Production entry/SL/TP2 geometry and never changes the
Production score, threshold, decision, or execution path. Historical rows do not
carry frozen entry-time L2 costs, so cost results are sensitivity scenarios only.
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


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _cost_r(round_trip_bps, row):
    """Convert a hypothetical round-trip cost in bps into R using frozen geometry."""
    g = row.get('geometry') or {}
    entry = _num(g.get('entry')); risk = _num(g.get('risk_abs'))
    if entry is None or risk is None or entry <= 0 or risk <= 0:
        return None
    return (float(round_trip_bps) / 10000.0) * entry / risk


def _historical_short_bucket(rows, threshold, *, trend_down_only=False):
    selected=[]
    for r in rows:
        g=r.get('geometry') or {}
        score=_num(r.get('score'))
        if g.get('direction') != 'SHORT' or score is None or score < threshold:
            continue
        if trend_down_only and str(r.get('regime') or '').upper() != 'TREND_DOWN':
            continue
        if not r.get('terminal') or r.get('r_multiple') is None:
            continue
        selected.append(r)
    gross=[float(r['r_multiple']) for r in selected]
    sensitivity={}
    for bps in (10,12,16,20):
        net=[]
        for r in selected:
            cr=_cost_r(bps,r)
            if cr is not None:
                net.append(float(r['r_multiple'])-cr)
        sensitivity[f'{bps}bps_round_trip']={
            'n':len(net),
            'avg_net_r':round(sum(net)/len(net),4) if net else None,
            'net_r':round(sum(net),4) if net else None,
            'positive_pct':round(100*sum(v>0 for v in net)/len(net),2) if net else None,
            'validated_live_cost':False,
        }
    return {
        'threshold_gte':threshold,
        'trend_down_only':trend_down_only,
        'n':len(gross),
        'gross_net_r':round(sum(gross),4) if gross else 0.0,
        'gross_avg_r':round(sum(gross)/len(gross),4) if gross else None,
        'gross_positive_pct':round(100*sum(v>0 for v in gross)/len(gross),2) if gross else None,
        'tp2_wins':sum(r.get('status')=='WIN_TP2' for r in selected),
        'losses':sum(float(r.get('r_multiple')) < 0 for r in selected),
        'sensitivity_only_not_validated_net':sensitivity,
        'sample_ge_30':len(gross)>=30,
    }


def historical_short_score_sweep(rows):
    """Evidence-only threshold comparison over settled canonical Production plans."""
    all_short={f'GTE_{cut}':_historical_short_bucket(rows,cut) for cut in (68,69,70,72)}
    trend_down={f'GTE_{cut}':_historical_short_bucket(rows,cut,trend_down_only=True) for cut in (68,69,70,72)}
    return {
        'schema':'ATLAS_HISTORICAL_SHORT_SCORE_SWEEP_V1_COUNTERFACTUAL',
        'role':'HISTORICAL_COUNTERFACTUAL_ONLY_NOT_FORWARD_PROOF',
        'source':'SETTLED_CANONICAL_PRODUCTION_PLANS',
        'episode_semantics':'FIRST_QUALIFIED_OBSERVATION_PER_CONTIGUOUS_SYMBOL_DIRECTION_EPISODE',
        'horizon_hours':12,
        'entry_sl_tp2_geometry_frozen_at_episode_start':True,
        'production_effect':'NONE',
        'can_override_production':False,
        'can_change_threshold':False,
        'production_threshold_unchanged':68,
        'exact_live_cost_available':False,
        'funding_included':False,
        'cost_policy':'10_12_16_20_BPS_ROUND_TRIP_SENSITIVITY_ONLY_NOT_VALIDATED_LIVE_COST',
        'all_short':all_short,
        'trend_down_short':trend_down,
        'promotion_policy':'DO_NOT_PROMOTE_FROM_HISTORICAL_SWEEP_ALONE; REQUIRE_PROSPECTIVE_POST_COST_EVIDENCE',
    }


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
    raw['historical_short_score_sweep']=historical_short_score_sweep(records)
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
                      'plan_shadow':raw['plan_shadow_summary'],
                      'historical_short_score_sweep':raw['historical_short_score_sweep']},indent=2))

if __name__=='__main__': main()
