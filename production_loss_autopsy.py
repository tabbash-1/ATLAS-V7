#!/usr/bin/env python3
"""ATLAS Production loss autopsy + entry-quality diagnostics.

Read-only research module. It never changes Production score, threshold,
direction, geometry, or execution eligibility. V2 diagnostics deliberately
separate stop-distance evidence from policy recommendations so legacy/frozen
geometry cannot silently drive a current Production change.
"""
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path

SCHEMA='ATLAS_PRODUCTION_LOSS_AUTOPSY_V2'
TIGHT_STOP_PCT=0.35
STOP_BANDS=(0.25,0.35,0.50,0.75,1.00)


def _f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None


def _mean(xs):
    xs=[x for x in xs if x is not None]
    return round(sum(xs)/len(xs),4) if xs else None


def _median(xs):
    xs=[x for x in xs if x is not None]
    return round(statistics.median(xs),4) if xs else None


def stop_distance_pct(r):
    g=r.get('geometry') or {}
    entry=_f(r.get('entry')); stop=_f(g.get('stop_loss'))
    if not entry or stop is None: return None
    return 100*abs(entry-stop)/entry


def geometry_generation(r):
    """Best-effort cohort tag; never invents a version when the ledger lacks one."""
    g=r.get('geometry') or {}
    for key in ('decision_engine_version','geometry_version','version'):
        value=g.get(key) or r.get(key)
        if value: return str(value)
    source=g.get('source') or r.get('geometry_source') or r.get('trade_plan_source')
    return str(source) if source else 'UNVERSIONED_LEGACY_OR_UNKNOWN'


def classify_loss(r):
    if r.get('path_outcome')!='LOSS': return None
    if r.get('tp1_reached'): return 'POST_TP1_REVERSAL'
    g=r.get('geometry') or {}
    rr=_f(g.get('rr_tp2'))
    stop_pct=stop_distance_pct(r)
    if stop_pct is not None and stop_pct < TIGHT_STOP_PCT: return 'STOP_TOO_TIGHT_CANDIDATE'
    if rr is not None and rr < 1: return 'INVALID_LEGACY_RR'
    return 'PRE_TP1_DIRECTION_OR_ENTRY_FAILURE'


def _band_counts(rows):
    distances=[stop_distance_pct(r) for r in rows]
    distances=[x for x in distances if x is not None]
    out={}
    lo=0.0
    for hi in STOP_BANDS:
        out[f'{lo:.2f}-{hi:.2f}%']=sum(lo <= x < hi for x in distances)
        lo=hi
    out[f'>={lo:.2f}%']=sum(x >= lo for x in distances)
    return out


def _cohorts(rows):
    out={}
    for name in sorted({geometry_generation(r) for r in rows}):
        sr=[r for r in rows if geometry_generation(r)==name]
        rs=[_f(r.get('r_multiple')) for r in sr]
        rs=[x for x in rs if x is not None]
        losses=[r for r in sr if (_f(r.get('r_multiple')) or 0)<0]
        out[name]={
            'n':len(sr),
            'wins':sum(x>0 for x in rs),
            'losses':sum(x<0 for x in rs),
            'net_r':round(sum(rs),4) if rs else None,
            'median_stop_distance_pct':_median([stop_distance_pct(r) for r in sr]),
            'tight_stop_losses':sum(classify_loss(r)=='STOP_TOO_TIGHT_CANDIDATE' for r in losses),
        }
    return out


def build_report(rows):
    rows=list(rows or [])
    terminal=[r for r in rows if r.get('terminal') and r.get('path_outcome') not in ('AMBIGUOUS','MARKET_DATA_ERROR')]
    wins=[r for r in terminal if _f(r.get('r_multiple')) is not None and _f(r.get('r_multiple'))>0]
    losses=[r for r in terminal if _f(r.get('r_multiple')) is not None and _f(r.get('r_multiple'))<0]
    causes=defaultdict(list)
    for r in losses: causes[classify_loss(r)].append(r)
    by_symbol={}
    for sym in sorted({str(r.get('symbol')) for r in terminal if r.get('symbol')}):
        sr=[r for r in terminal if str(r.get('symbol'))==sym]
        rs=[_f(r.get('r_multiple')) for r in sr]; rs=[x for x in rs if x is not None]
        by_symbol[sym]={'n':len(sr),'positive':sum(x>0 for x in rs),'negative':sum(x<0 for x in rs),'net_r':round(sum(rs),4) if rs else None}
    loss_rows=[]
    for r in losses:
        g=r.get('geometry') or {}
        loss_rows.append({
            'id':r.get('id'),'symbol':r.get('symbol'),'direction':r.get('direction'),
            'score':_f(r.get('score')),'cause':classify_loss(r),
            'geometry_generation':geometry_generation(r),
            'tp1_reached':bool(r.get('tp1_reached')),'rr_tp2':_f(g.get('rr_tp2')),
            'stop_distance_pct':round(stop_distance_pct(r),4) if stop_distance_pct(r) is not None else None,
            'r_multiple':_f(r.get('r_multiple')),
        })
    generations=_cohorts(terminal)
    unknown_only=bool(generations) and set(generations)=={'UNVERSIONED_LEGACY_OR_UNKNOWN'}
    tight_loss_count=sum(classify_loss(r)=='STOP_TOO_TIGHT_CANDIDATE' for r in losses)
    evidence={
        'tight_stop_threshold_pct':TIGHT_STOP_PCT,
        'terminal_stop_distance_bands':_band_counts(terminal),
        'loss_stop_distance_bands':_band_counts(losses),
        'median_stop_distance_pct_wins':_median([stop_distance_pct(r) for r in wins]),
        'median_stop_distance_pct_losses':_median([stop_distance_pct(r) for r in losses]),
        'geometry_generations':generations,
        'generation_metadata_complete':not unknown_only,
        'tight_stop_loss_share_pct':round(100*tight_loss_count/len(losses),2) if losses else None,
    }
    recommendation={
        'action':'COLLECT_POST_FIX_COHORT' if unknown_only else 'COMPARE_GEOMETRY_GENERATIONS',
        'change_production_stop_policy_now':False,
        'reason':'Ledger geometry is unversioned/mixed; do not attribute legacy tight stops to the current ATR-aware engine.' if unknown_only else 'Compare current geometry generation against legacy cohorts before any Production stop-policy change.',
        'minimum_post_fix_terminal_sample':30,
    }
    return {
        'schema':SCHEMA,'terminal':len(terminal),'wins':len(wins),'losses':len(losses),
        'win_rate_pct':round(100*len(wins)/(len(wins)+len(losses)),2) if wins or losses else None,
        'net_r':round(sum(_f(r.get('r_multiple')) or 0 for r in terminal),4),
        'avg_win_score':_mean([_f(r.get('score')) for r in wins]),
        'avg_loss_score':_mean([_f(r.get('score')) for r in losses]),
        'loss_cause_counts':{k:len(v) for k,v in sorted(causes.items())},
        'losses_after_tp1':sum(bool(r.get('tp1_reached')) for r in losses),
        'by_symbol':by_symbol,'entry_quality_evidence':evidence,
        'research_recommendation':recommendation,'loss_rows':loss_rows,
        'production_threshold':68,'production_threshold_changed':False,
        'production_score_adjustment':0,'production_stop_policy_changed':False,
        'research_only':True,
    }


def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',required=True); p.add_argument('--output',default='status/production-loss-autopsy.json'); a=p.parse_args()
    x=json.loads(Path(a.input).read_text()); rows=x.get('rows') if isinstance(x,dict) else x
    out=build_report(rows or []); Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,sort_keys=True))
if __name__=='__main__': main()
