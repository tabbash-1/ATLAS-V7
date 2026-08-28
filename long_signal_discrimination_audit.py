#!/usr/bin/env python3
"""Audit whether existing V6 components discriminate good vs bad LONG setups.

Scope: LONG rows retained by the accepted combined research shadow, evaluated at
12h. This is a diagnostic of representation/ranking quality, not a new filter.
It checks score/component rank correlation, winner-vs-loser separation, temporal
stability, and leave-one-symbol-out sign stability using only persisted fields.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as combined
import counterfactual_episode_evaluation as paired

OUT = Path('status/long-signal-discrimination-audit.json')
SCHEMA = 'ATLAS_V6_LONG_SIGNAL_DISCRIMINATION_AUDIT_V1'
H = 12

NUMERIC_FEATURES = {
    'score': lambda r: base.fnum(r.get('corrected_score')),
    'trend_base': lambda r: base.fnum(r.get('trend_base')),
    'relative_volume': lambda r: base.fnum(r.get('relative_volume_replayed')),
    'volume_bonus': lambda r: base.fnum(r.get('volume_bonus')),
    'rs_adjustment': lambda r: base.fnum(r.get('rs_adjustment')),
    'futures_adjustment': lambda r: base.fnum(r.get('futures_adjustment')),
    'obstacle_adjustment': lambda r: base.fnum(r.get('obstacle_adjustment')),
    'direction_votes': lambda r: base.fnum(r.get('direction_votes')),
}
CAT_FEATURES = ('rs_reason','futures_reason','obstacle_reason','symbol')


def rankdata(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0]*len(values)
    i=0
    while i < len(order):
        j=i
        while j+1 < len(order) and values[order[j+1]] == values[order[i]]:
            j+=1
        rank=(i+j+2)/2.0
        for k in range(i,j+1): ranks[order[k]]=rank
        i=j+1
    return ranks


def pearson(xs, ys):
    if len(xs) < 3: return None
    mx,my=statistics.mean(xs),statistics.mean(ys)
    dx=[x-mx for x in xs]; dy=[y-my for y in ys]
    den=math.sqrt(sum(x*x for x in dx)*sum(y*y for y in dy))
    if den == 0: return None
    return sum(a*b for a,b in zip(dx,dy))/den


def spearman(xs, ys):
    if len(xs) < 3: return None
    return pearson(rankdata(xs),rankdata(ys))


def feature_diag(rows, getter):
    pairs=[]
    for r in rows:
        x=getter(r); y=base.fnum(r.get('return_12h_pct'))
        if x is not None and y is not None: pairs.append((r,x,y))
    xs=[x for _,x,_ in pairs]; ys=[y for *_,y in pairs]
    winners=[x for _,x,y in pairs if y>0]; losers=[x for _,x,y in pairs if y<=0]
    rho=spearman(xs,ys)
    return {
        'n':len(pairs),
        'spearman_rho':None if rho is None else round(rho,4),
        'winner_mean':None if not winners else round(statistics.mean(winners),4),
        'loser_mean':None if not losers else round(statistics.mean(losers),4),
        'winner_minus_loser':None if not winners or not losers else round(statistics.mean(winners)-statistics.mean(losers),4),
    }


def category_diag(rows, field):
    g=defaultdict(list)
    for r in rows: g[str(r.get(field) or 'UNKNOWN')].append(r)
    out={}
    for k,v in sorted(g.items()): out[k]=base.stats(v,H)
    return out


def long_pool(hourly):
    return [r for r in hourly if r.get('direction')=='LONG' and combined.candidate_qualified(r)]


def lane_diag(rows):
    eps=base.independent(long_pool(rows),H)
    return {
        'outcomes':base.stats(eps,H),
        'numeric':{name:feature_diag(eps,getter) for name,getter in NUMERIC_FEATURES.items()},
        'categorical':{f:category_diag(eps,f) for f in CAT_FEATURES},
        'episodes':len(eps),
    }


def loo_feature_signs(rows):
    eps=base.independent(long_pool(rows),H)
    symbols=sorted({r['symbol'] for r in eps})
    out={}
    for name,getter in NUMERIC_FEATURES.items():
        vals=[]
        for s in symbols:
            d=feature_diag([r for r in eps if r['symbol']!=s],getter)
            vals.append({'left_out_symbol':s,'n':d['n'],'spearman_rho':d['spearman_rho']})
        finite=[x['spearman_rho'] for x in vals if x['spearman_rho'] is not None]
        out[name]={
            'leave_one_symbol_out':vals,
            'all_positive':bool(finite) and all(x>0 for x in finite),
            'all_negative':bool(finite) and all(x<0 for x in finite),
            'mixed_or_insufficient':not finite or not (all(x>0 for x in finite) or all(x<0 for x in finite)),
        }
    return out


def run(path=base.SRC):
    snaps=base.load_snapshots(path); prices=base.build_price_series(snaps)
    rows,excluded=base.flatten(snaps); base.settle(rows,prices); hourly=base.hourly_dedupe(rows)
    train,holdout,cutoff=paired.split_60_40(hourly)
    lanes={'full':lane_diag(hourly),'train':lane_diag(train),'holdout':lane_diag(holdout)}
    loo=loo_feature_signs(hourly)

    stable_predictors=[]; anti_predictors=[]
    for name in NUMERIC_FEATURES:
        a=lanes['train']['numeric'][name]; b=lanes['holdout']['numeric'][name]; c=lanes['full']['numeric'][name]
        if min(a['n'],b['n']) < 3: continue
        ar,br=a['spearman_rho'],b['spearman_rho']
        if ar is None or br is None: continue
        if ar>0 and br>0 and loo[name]['all_positive']:
            stable_predictors.append({'feature':name,'full':c,'train':a,'holdout':b,'loo':loo[name]})
        if ar<0 and br<0 and loo[name]['all_negative']:
            anti_predictors.append({'feature':name,'full':c,'train':a,'holdout':b,'loo':loo[name]})

    score_full=lanes['full']['numeric']['score']['spearman_rho']
    score_train=lanes['train']['numeric']['score']['spearman_rho']
    score_hold=lanes['holdout']['numeric']['score']['spearman_rho']
    if score_train is not None and score_hold is not None and score_train<=0 and score_hold<=0:
        diagnosis='LONG_SCORE_LACKS_POSITIVE_OUTCOME_DISCRIMINATION'
        next_step='Do not raise/lower the LONG threshold. Build a research-only LONG regime representation candidate from existing stable predictors or add path/regime features only if already available historically.'
    elif stable_predictors:
        diagnosis='LONG_SCORE_HAS_PARTIAL_DISCRIMINATION_WITH_STABLE_COMPONENTS'
        next_step='Test one isolated reweighting shadow for the strongest stable component using paired counterfactual methodology.'
    else:
        diagnosis='LONG_DISCRIMINATION_INCONCLUSIVE_OR_UNSTABLE'
        next_step='Do not add a threshold or veto. Inspect historical path/regime features and expand representation only where data already exists.'

    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'ACCEPTED_COMBINED_SHADOW_LONG_12H',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'lanes':lanes,'leave_one_symbol_out':loo,
        'stable_positive_numeric_predictors':stable_predictors,
        'stable_negative_numeric_predictors':anti_predictors,
        'score_discrimination':{'full_spearman_rho':score_full,'train_spearman_rho':score_train,'holdout_spearman_rho':score_hold},
        'diagnosis':diagnosis,'next_step':next_step,
        'production_change_recommended':False,
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'combined_shadow_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'coverage':r['coverage'],'long_outcomes':{k:v['outcomes'] for k,v in r['lanes'].items()},'score_discrimination':r['score_discrimination'],'stable_positive_numeric_predictors':r['stable_positive_numeric_predictors'],'stable_negative_numeric_predictors':r['stable_negative_numeric_predictors'],'diagnosis':r['diagnosis'],'next_step':r['next_step'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__': main()
