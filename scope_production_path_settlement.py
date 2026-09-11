#!/usr/bin/env python3
"""Scope offline path settlement without mislabeling shadow outcomes as realized P&L.

ATLAS live execution is disabled. Therefore no modelled/Execution-Ready path may
be called realized R. We retain research cohorts while publishing an empty
realized summary until a real fill ledger exists.

The historical SHORT score sweep is counterfactual research only. It reuses the
already-settled canonical Production entry/SL/TP2 geometry and never changes the
Production score, threshold, decision, or execution path. Historical rows do not
carry frozen entry-time L2 costs, so cost results are sensitivity scenarios only.

Historical factor attribution joins each settled episode back to the exact
recorded Production snapshot by captured_at + symbol. It never reconstructs or
backfills a missing score component and remains descriptive, research-only
counterfactual evidence.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from execution_cost_model import cost_bps_to_r

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'status/production-path-settlement-latest.json'
HISTORY = ROOT / 'status/history/production-snapshots.jsonl'
SCHEMA = 'ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V4_NO_FAKE_REALIZED_R'

FACTOR_KEYS = {
    'trend_base': 'trend_base',
    'paced_volume_bonus': 'volume_bonus',
    'relative_strength_adjustment': 'relative_strength_adjustment',
    'futures_adjustment': 'futures_adjustment',
    'prior_structure_obstacle_adjustment': 'obstacle_adjustment',
}


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
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _cost_r(round_trip_bps, row):
    """Convert hypothetical round-trip bps to R through the canonical cost model."""
    g = row.get('geometry') or {}
    entry = _num(g.get('entry')); risk = _num(g.get('risk_abs'))
    if entry is None or risk is None or entry <= 0 or risk <= 0:
        return None
    try:
        return cost_bps_to_r(round_trip_bps, entry=entry, risk_abs=risk)
    except Exception:
        return None


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


def _iso(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace('Z','+00:00')).isoformat()
    except Exception:
        return None


def _snapshot_decision_index():
    """Exact decision-time evidence only; never synthesize missing historical fields."""
    out={}
    malformed=0
    if not HISTORY.exists():
        return out, malformed
    for line in HISTORY.read_text(errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            snap=json.loads(line)
        except Exception:
            malformed += 1
            continue
        captured=_iso(snap.get('captured_at'))
        if not captured:
            continue
        for symbol, decision in (snap.get('decisions') or {}).items():
            if isinstance(decision,dict):
                out[(captured,str(symbol))]=decision
    return out, malformed


def _pearson(xs, ys):
    n=len(xs)
    if n < 3 or n != len(ys):
        return None
    mx=sum(xs)/n; my=sum(ys)/n
    dx=[x-mx for x in xs]; dy=[y-my for y in ys]
    den=(sum(x*x for x in dx)*sum(y*y for y in dy))**0.5
    if den <= 0:
        return None
    return sum(a*b for a,b in zip(dx,dy))/den


def _mean(vals):
    return sum(vals)/len(vals) if vals else None


def _factor_stats(pairs):
    """pairs = (factor value, gross R, record). Descriptive only."""
    xs=[p[0] for p in pairs]; gross=[p[1] for p in pairs]
    pos=[p[0] for p in pairs if p[1] > 0]
    neg=[p[0] for p in pairs if p[1] < 0]
    costs={}
    for bps in (10,12,16,20):
        nx=[]; ny=[]
        for x,r,row in pairs:
            cr=_cost_r(bps,row)
            if cr is not None:
                nx.append(x); ny.append(r-cr)
        corr=_pearson(nx,ny)
        costs[f'{bps}bps_round_trip']={
            'n':len(nx),
            'corr_factor_vs_net_r':round(corr,4) if corr is not None else None,
            'avg_net_r':round(_mean(ny),4) if ny else None,
            'validated_live_cost':False,
        }
    corr=_pearson(xs,gross)
    unique=sorted({round(x,6) for x in xs})
    return {
        'n':len(pairs),
        'corr_factor_vs_gross_r':round(corr,4) if corr is not None else None,
        'mean_factor_positive_r':round(_mean(pos),4) if pos else None,
        'mean_factor_negative_r':round(_mean(neg),4) if neg else None,
        'mean_factor_all':round(_mean(xs),4) if xs else None,
        'unique_values':unique[:30],
        'unique_value_count':len(unique),
        'cost_sensitivity':costs,
        'association_only_not_causal':True,
    }


def historical_short_factor_attribution(rows):
    idx, malformed=_snapshot_decision_index()
    short_rows=[r for r in rows if (r.get('geometry') or {}).get('direction')=='SHORT' and r.get('terminal') and r.get('r_multiple') is not None]
    matched=[]
    missing_snapshot=0
    missing_attribution=0
    for r in short_rows:
        decision=idx.get((_iso(r.get('captured_at')),str(r.get('symbol'))))
        if not decision:
            missing_snapshot += 1
            continue
        attribution=decision.get('score_attribution')
        if not isinstance(attribution,dict):
            missing_attribution += 1
            continue
        matched.append((r,attribution))

    factors={}
    for official_name, stored_key in FACTOR_KEYS.items():
        pairs=[]
        for row, attribution in matched:
            value=_num(attribution.get(stored_key))
            if value is None:
                continue
            pairs.append((value,float(row['r_multiple']),row))
        factors[official_name]=_factor_stats(pairs)

    complete=[]
    for row, attribution in matched:
        vals={name:_num(attribution.get(key)) for name,key in FACTOR_KEYS.items()}
        if all(v is not None for v in vals.values()):
            complete.append(row)

    return {
        'schema':'ATLAS_HISTORICAL_SHORT_FACTOR_ATTRIBUTION_V1_DECISION_TIME_JOIN',
        'role':'HISTORICAL_DESCRIPTIVE_ONLY_NOT_FORWARD_PROOF',
        'source_settlement':'status/production-path-settlement-latest.json',
        'source_decision_history':'status/history/production-snapshots.jsonl',
        'join_key':'NORMALIZED_CAPTURED_AT_PLUS_SYMBOL',
        'episode_semantics':'FIRST_QUALIFIED_OBSERVATION_PER_CONTIGUOUS_SYMBOL_DIRECTION_EPISODE',
        'decision_time_values_only':True,
        'backfill_performed':False,
        'missing_values_reconstructed':False,
        'terminal_short_episodes':len(short_rows),
        'matched_snapshot_attribution_episodes':len(matched),
        'complete_five_factor_episodes':len(complete),
        'missing_snapshot_matches':missing_snapshot,
        'missing_score_attribution':missing_attribution,
        'malformed_history_lines':malformed,
        'factors':factors,
        'exact_live_cost_available':False,
        'funding_included':False,
        'cost_policy':'CANONICAL_EXECUTION_COST_MODEL_CONVERSION_WITH_10_12_16_20_BPS_SENSITIVITY_ONLY',
        'production_effect':'NONE',
        'can_override_production':False,
        'can_change_threshold':False,
        'production_threshold_unchanged':68,
        'interpretation_rule':'CORRELATIONS_AND_WIN_LOSS_MEANS_ARE DESCRIPTIVE ASSOCIATIONS; DO NOT REWEIGHT BEFORE PROSPECTIVE_POST_COST_N_GTE_30',
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
    raw['historical_short_factor_attribution']=historical_short_factor_attribution(records)
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
                      'historical_short_score_sweep':raw['historical_short_score_sweep'],
                      'historical_short_factor_attribution':raw['historical_short_factor_attribution']},indent=2))

if __name__=='__main__': main()
