#!/usr/bin/env python3
"""Audit LONG representation across the full V6 score spectrum.

Unlike the accepted-shadow LONG audit, this uses every independent V6 LONG
observation with a settled +12h outcome, including sub-threshold rows. The goal
is to determine which existing components genuinely rank LONG outcomes and
which components are anti-predictive before any qualification/filtering.

Research-only. No Production threshold or formula changes.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import counterfactual_episode_evaluation as paired
import long_signal_discrimination_audit as disc

OUT = Path('status/v6-long-representation-audit.json')
SCHEMA = 'ATLAS_V6_LONG_REPRESENTATION_AUDIT_V1'
H = 12

NUMERIC = disc.NUMERIC_FEATURES
CATEGORICAL = ('rs_reason','futures_reason','obstacle_reason','symbol')


def all_long(rows):
    return [r for r in rows if r.get('direction') == 'LONG']


def episodes(rows):
    return base.independent(all_long(rows), H)


def score_band(score):
    x = int(base.round_score(score))
    if x < 52: return '<52'
    if x < 56: return '52-55'
    if x < 60: return '56-59'
    if x < 64: return '60-63'
    if x < 68: return '64-67'
    if x < 72: return '68-71'
    if x < 76: return '72-75'
    return '76+'


def grouped_stats(rows, key_fn):
    g=defaultdict(list)
    for r in rows: g[str(key_fn(r))].append(r)
    return {k:base.stats(v,H) for k,v in sorted(g.items())}


def numeric_lane(eps):
    return {name:disc.feature_diag(eps,getter) for name,getter in NUMERIC.items()}


def categorical_lane(eps):
    return {
        'score_band': grouped_stats(eps, lambda r: score_band(r.get('corrected_score'))),
        **{f:grouped_stats(eps, lambda r, f=f: r.get(f) or 'UNKNOWN') for f in CATEGORICAL},
    }


def lane(rows):
    eps=episodes(rows)
    return {'episodes':len(eps),'outcomes':base.stats(eps,H),'numeric':numeric_lane(eps),'categorical':categorical_lane(eps)}


def loo(rows):
    eps=episodes(rows); syms=sorted({r['symbol'] for r in eps})
    out={}
    for name,getter in NUMERIC.items():
        vals=[]
        for s in syms:
            d=disc.feature_diag([r for r in eps if r['symbol'] != s],getter)
            vals.append({'left_out_symbol':s,'n':d['n'],'spearman_rho':d['spearman_rho'],'winner_minus_loser':d['winner_minus_loser']})
        finite=[x['spearman_rho'] for x in vals if x['spearman_rho'] is not None]
        out[name]={
            'leave_one_symbol_out':vals,
            'all_positive':bool(finite) and all(v>0 for v in finite),
            'all_negative':bool(finite) and all(v<0 for v in finite),
            'mixed_or_insufficient':not finite or not (all(v>0 for v in finite) or all(v<0 for v in finite)),
        }
    return out


def stable_components(lanes, loo_map):
    positive=[]; negative=[]
    for name in NUMERIC:
        f=lanes['full']['numeric'][name]; t=lanes['train']['numeric'][name]; h=lanes['holdout']['numeric'][name]
        if min(t['n'],h['n']) < 5: continue
        tr=t['spearman_rho']; hr=h['spearman_rho']
        if tr is None or hr is None: continue
        item={'feature':name,'full':f,'train':t,'holdout':h,'loo':loo_map[name]}
        if tr>0 and hr>0 and loo_map[name]['all_positive']: positive.append(item)
        if tr<0 and hr<0 and loo_map[name]['all_negative']: negative.append(item)
    positive.sort(key=lambda x:-(x['full'].get('spearman_rho') or 0))
    negative.sort(key=lambda x:(x['full'].get('spearman_rho') or 0))
    return positive,negative


def category_stability(lanes, field):
    keys=set(lanes['train']['categorical'][field]) | set(lanes['holdout']['categorical'][field])
    out=[]
    for k in sorted(keys):
        t=lanes['train']['categorical'][field].get(k,{'n':0,'mean_pct':None,'win_rate_pct':None})
        h=lanes['holdout']['categorical'][field].get(k,{'n':0,'mean_pct':None,'win_rate_pct':None})
        f=lanes['full']['categorical'][field].get(k,{'n':0,'mean_pct':None,'win_rate_pct':None})
        stable_pos=t.get('n',0)>=3 and h.get('n',0)>=3 and t.get('mean_pct') is not None and h.get('mean_pct') is not None and t['mean_pct']>0 and h['mean_pct']>0
        stable_neg=t.get('n',0)>=3 and h.get('n',0)>=3 and t.get('mean_pct') is not None and h.get('mean_pct') is not None and t['mean_pct']<0 and h['mean_pct']<0
        if stable_pos or stable_neg:
            out.append({'bucket':k,'stable_positive':stable_pos,'stable_negative':stable_neg,'full':f,'train':t,'holdout':h})
    return out


def run(path=base.SRC):
    snaps=base.load_snapshots(path); prices=base.build_price_series(snaps)
    rows,excluded=base.flatten(snaps); base.settle(rows,prices); hourly=base.hourly_dedupe(rows)
    train_rows,hold_rows,cutoff=paired.split_60_40(hourly)
    lanes={'full':lane(hourly),'train':lane(train_rows),'holdout':lane(hold_rows)}
    loo_map=loo(hourly)
    pos,neg=stable_components(lanes,loo_map)
    cat={f:category_stability(lanes,f) for f in ('score_band',)+CATEGORICAL}

    score=lanes['full']['numeric']['score']; score_t=lanes['train']['numeric']['score']; score_h=lanes['holdout']['numeric']['score']
    score_consistently_positive=score_t.get('spearman_rho') is not None and score_h.get('spearman_rho') is not None and score_t['spearman_rho']>0 and score_h['spearman_rho']>0
    if not score_consistently_positive and pos:
        diagnosis='LONG_TOTAL_SCORE_FAILS_WHILE_ONE_OR_MORE_COMPONENTS_RETAIN_POSITIVE_SIGNAL'
        next_step='Build ONE direction-specific LONG research formula from the strongest stable positive component, preserving all existing safety gates, then evaluate with paired dynamic/fixed methodology.'
    elif not score_consistently_positive and not pos:
        diagnosis='LONG_EXISTING_COMPONENT_SET_LACKS_STABLE_POSITIVE_RANKING_SIGNAL'
        next_step='Do not tune weights or threshold. Identify historically available regime/path features not represented in V6 LONG scoring before proposing a new formula.'
    else:
        diagnosis='LONG_SCORE_HAS_POSITIVE_GLOBAL_RANKING_REVIEW_THRESHOLD_INTERACTIONS'
        next_step='Inspect why qualification subset becomes anti-predictive despite positive global score ranking; do not change Production directly.'

    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'ALL_INDEPENDENT_V6_LONG_12H_ACROSS_SCORE_SPECTRUM',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'full_long_episodes':lanes['full']['episodes'],'train_long_episodes':lanes['train']['episodes'],'holdout_long_episodes':lanes['holdout']['episodes'],'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'lanes':lanes,'leave_one_symbol_out':loo_map,
        'stable_positive_numeric_components':pos,'stable_negative_numeric_components':neg,
        'stable_categorical_buckets':cat,
        'score_global_discrimination':{'full':score,'train':score_t,'holdout':score_h},
        'diagnosis':diagnosis,'next_step':next_step,
        'production_change_recommended':False,
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'coverage':r['coverage'],'score_global_discrimination':r['score_global_discrimination'],'stable_positive_numeric_components':r['stable_positive_numeric_components'],'stable_negative_numeric_components':r['stable_negative_numeric_components'],'stable_categorical_buckets':r['stable_categorical_buckets'],'diagnosis':r['diagnosis'],'next_step':r['next_step'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__': main()
