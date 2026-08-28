#!/usr/bin/env python3
"""Diagnose why the accepted combined shadow weakens from 12h to 24h.

Uses ONLY fields already persisted in V6 Production snapshots. The analysis is
not a new scoring rule. It asks whether weak 24h results are caused by:
- bad selections that are already losing at 12h, or
- 12h winners that give back/reverse between 12h and 24h.

Episodes are anchored at 24h independence so the same observations are compared
across 12h and 24h. Train/holdout are time-split before descriptive grouping.
Production is untouched.
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as combined
import post_combined_shadow_residual_autopsy as factors
import counterfactual_episode_evaluation as paired

OUT = Path('status/horizon-transition-gap-analysis.json')
SCHEMA = 'ATLAS_V6_HORIZON_TRANSITION_GAP_ANALYSIS_V1'


def combined_qualified(r):
    return combined.candidate_qualified(r)


def transition(r):
    r12 = base.fnum(r.get('return_12h_pct'))
    r24 = base.fnum(r.get('return_24h_pct'))
    if r12 is None or r24 is None:
        return None
    if r12 > 0 and r24 > 0: return 'WIN12_WIN24'
    if r12 > 0 and r24 <= 0: return 'WIN12_LOSS24'
    if r12 <= 0 and r24 > 0: return 'LOSS12_WIN24'
    return 'LOSS12_LOSS24'


def episode_view(r):
    r12 = base.fnum(r.get('return_12h_pct'))
    r24 = base.fnum(r.get('return_24h_pct'))
    return {
        'captured_at': r['captured_at'].isoformat(),
        'symbol': r['symbol'], 'direction': r['direction'],
        'score': r.get('corrected_score'), 'trend_base': r.get('trend_base'),
        'rs_reason': r.get('rs_reason'), 'futures_reason': r.get('futures_reason'),
        'obstacle_reason': r.get('obstacle_reason'),
        'relative_volume_replayed': r.get('relative_volume_replayed'),
        'return_12h_pct': r12, 'return_24h_pct': r24,
        'post_12h_change_pct': None if r12 is None or r24 is None else round(r24-r12, 4),
        'transition': transition(r),
    }


def transition_stats(rows):
    usable = [r for r in rows if transition(r)]
    counts = defaultdict(int)
    for r in usable: counts[transition(r)] += 1
    n = len(usable)
    win12 = [r for r in usable if base.fnum(r.get('return_12h_pct'), 0) > 0]
    reversals = [r for r in win12 if base.fnum(r.get('return_24h_pct'), 0) <= 0]
    persist = [r for r in win12 if base.fnum(r.get('return_24h_pct'), 0) > 0]
    changes = [(base.fnum(r.get('return_24h_pct')) - base.fnum(r.get('return_12h_pct'))) for r in usable]
    winner_changes = [(base.fnum(r.get('return_24h_pct')) - base.fnum(r.get('return_12h_pct'))) for r in win12]
    return {
        'n': n,
        'counts': dict(sorted(counts.items())),
        'win_12h_n': len(win12),
        'win12_to_loss24_n': len(reversals),
        'win12_to_loss24_rate_pct': None if not win12 else round(100*len(reversals)/len(win12), 2),
        'win12_persist24_n': len(persist),
        'mean_post_12h_change_pct': None if not changes else round(statistics.mean(changes), 4),
        'median_post_12h_change_pct': None if not changes else round(statistics.median(changes), 4),
        'mean_post_12h_change_for_12h_winners_pct': None if not winner_changes else round(statistics.mean(winner_changes), 4),
        'median_post_12h_change_for_12h_winners_pct': None if not winner_changes else round(statistics.median(winner_changes), 4),
        'return_12h': base.stats(usable, 12),
        'return_24h': base.stats(usable, 24),
    }


def utc_session(r):
    h = r['captured_at'].hour
    if 0 <= h < 6: return 'UTC_00_05'
    if 6 <= h < 12: return 'UTC_06_11'
    if 12 <= h < 18: return 'UTC_12_17'
    return 'UTC_18_23'


def feature_map(r):
    x = factors.keymap(r)
    x['trend_base'] = str(int(round(base.fnum(r.get('trend_base'),0) or 0)))
    x['futures_reason'] = str(r.get('futures_reason') or 'UNKNOWN')
    x['utc_session'] = utc_session(r)
    x['symbol'] = r['symbol']
    return x


def bucket_summary(rows):
    s = transition_stats(rows)
    return {
        'n': s['n'],
        'win12_to_loss24_rate_pct': s['win12_to_loss24_rate_pct'],
        'mean_post_12h_change_pct': s['mean_post_12h_change_pct'],
        'mean_post_12h_change_for_12h_winners_pct': s['mean_post_12h_change_for_12h_winners_pct'],
        'return_12h_mean_pct': s['return_12h']['mean_pct'],
        'return_24h_mean_pct': s['return_24h']['mean_pct'],
        'win12_n': s['win_12h_n'],
    }


def grouped(rows, factor):
    g = defaultdict(list)
    for r in rows:
        g[feature_map(r).get(factor,'UNKNOWN')].append(r)
    return {k:bucket_summary(v) for k,v in sorted(g.items())}


def stable_reversal_buckets(train, holdout, full):
    fields = [
        'direction','relative_strength','obstacle','volume_bin','shadow_score_bin',
        'direction_x_rs','direction_x_obstacle','direction_x_volume','direction_x_score',
        'rs_x_obstacle','volume_x_obstacle','score_x_rs','score_x_obstacle',
        'trend_base','futures_reason','utc_session','symbol',
    ]
    tables, stable = {}, []
    for field in fields:
        ft, fh, ff = grouped(train,field), grouped(holdout,field), grouped(full,field)
        tables[field] = {'full':ff,'train':ft,'holdout':fh}
        for bucket in sorted(set(ft)|set(fh)|set(ff)):
            a,b,c = ft.get(bucket,{}), fh.get(bucket,{}), ff.get(bucket,{})
            # Stable horizon-decay bucket: enough 12h winners in both lanes,
            # majority of those winners reverse OR winner post-12h change is
            # materially negative in both lanes. This is diagnostic only.
            enough = a.get('win12_n',0) >= 2 and b.get('win12_n',0) >= 2
            ar = a.get('win12_to_loss24_rate_pct')
            br = b.get('win12_to_loss24_rate_pct')
            ac = a.get('mean_post_12h_change_for_12h_winners_pct')
            bc = b.get('mean_post_12h_change_for_12h_winners_pct')
            reversal = enough and ar is not None and br is not None and ar >= 50 and br >= 50
            decay = enough and ac is not None and bc is not None and ac < -0.25 and bc < -0.25
            if reversal or decay:
                stable.append({
                    'factor':field,'bucket':bucket,
                    'stable_reversal':bool(reversal),'stable_winner_decay':bool(decay),
                    'full':c,'train':a,'holdout':b,
                })
    stable.sort(key=lambda x:(
        -int(x['stable_reversal']), -int(x['stable_winner_decay']),
        -(x['full'].get('win12_n') or 0),
        x['full'].get('mean_post_12h_change_for_12h_winners_pct') or 999,
    ))
    return tables, stable


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    pool = [r for r in hourly if combined_qualified(r)]
    # Freeze 24h anchors first, then compare the SAME episodes at 12 and 24.
    anchors = base.independent(pool,24)
    anchors = [r for r in anchors if transition(r)]
    train, holdout, cutoff = paired.split_60_40(anchors)
    tables, stable = stable_reversal_buckets(train,holdout,anchors)
    overall = {'full':transition_stats(anchors),'train':transition_stats(train),'holdout':transition_stats(holdout)}

    full = overall['full']
    reversal_share = full.get('win12_to_loss24_rate_pct')
    winner_decay = full.get('mean_post_12h_change_for_12h_winners_pct')
    if reversal_share is not None and reversal_share >= 40 and winner_decay is not None and winner_decay < 0:
        diagnosis = 'HORIZON_DECAY_AFTER_12H_IS_MATERIAL'
        next_step = 'Test a research-only horizon-aware holding/exit overlay on the accepted combined shadow. Do not add another entry veto.'
    elif full['return_12h'].get('mean_pct',0) <= 0:
        diagnosis = 'SELECTION_WEAK_BEFORE_12H'
        next_step = 'Improve entry selection/regime representation before considering exit policy.'
    else:
        diagnosis = 'MIXED_HORIZON_GAP_REQUIRES_DEEPER_PATH_ANALYSIS'
        next_step = 'Inspect path-dependent excursion/volatility data if already available; do not invent a new veto.'

    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'ACCEPTED_COMBINED_SHADOW_24H_FIXED_EPISODE_ANCHORS',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'combined_pool_hours':len(pool),'fixed_24h_episodes_with_12h_and_24h':len(anchors),'train_episodes':len(train),'holdout_episodes':len(holdout),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'overall_transition':overall,
        'stable_horizon_decay_buckets':stable,
        'factor_tables':tables,
        'diagnosis':diagnosis,'next_step':next_step,
        'production_change_recommended':False,
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'combined_shadow_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run(); OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'coverage':r['coverage'],'overall_transition':r['overall_transition'],'stable_horizon_decay_buckets':r['stable_horizon_decay_buckets'][:10],'diagnosis':r['diagnosis'],'next_step':r['next_step'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__': main()
