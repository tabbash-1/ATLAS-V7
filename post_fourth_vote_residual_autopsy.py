#!/usr/bin/env python3
"""Residual V6 directional-loss autopsy after the fourth-vote shadow filter.

Diagnostic only. Uses the already-recorded snapshot history and asks which
remaining context buckets are persistently weak after the best validated shadow
filter is applied. It does not propose or apply a Production change.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import fourth_vote_demotion_shadow as fourth

OUT = Path('status/post-fourth-vote-residual-autopsy.json')
SCHEMA = 'ATLAS_V6_POST_FOURTH_VOTE_RESIDUAL_AUTOPSY_V1'


def volume_bin(rv):
    x = base.fnum(rv, 0.0) or 0.0
    if x < 0.5: return '<0.50'
    if x < 0.8: return '0.50-0.79'
    if x < 1.0: return '0.80-0.99'
    if x < 1.5: return '1.00-1.49'
    return '>=1.50'


def score_bin(score):
    x = int(base.round_score(score))
    if x <= 69: return '68-69'
    if x <= 72: return '70-72'
    if x <= 76: return '73-76'
    return '77+'


def keymap(r):
    obstacle = str(r.get('obstacle_reason') or 'UNKNOWN')
    rs = str(r.get('rs_reason') or 'UNKNOWN')
    direction = str(r.get('direction') or 'UNKNOWN')
    vb = volume_bin(r.get('relative_volume_replayed'))
    sb = score_bin(fourth.candidate_score(r))
    return {
        'direction': direction,
        'obstacle': obstacle,
        'relative_strength': rs,
        'volume_bin': vb,
        'shadow_score_bin': sb,
        'direction_x_obstacle': f'{direction}|{obstacle}',
        'direction_x_rs': f'{direction}|{rs}',
        'direction_x_volume': f'{direction}|{vb}',
        'score_x_obstacle': f'{sb}|{obstacle}',
    }


def split(rows):
    rows = sorted(rows, key=lambda r: r['captured_at'])
    hours = sorted({r['captured_at'].replace(minute=0, second=0, microsecond=0) for r in rows})
    if len(hours) < 2: return rows, [], None
    idx = max(1, min(len(hours)-1, int(len(hours)*0.60)))
    cutoff = hours[idx]
    return [r for r in rows if r['captured_at'] < cutoff], [r for r in rows if r['captured_at'] >= cutoff], cutoff


def grouped(rows, field, horizon):
    buckets = defaultdict(list)
    for r in rows:
        buckets[keymap(r)[field]].append(r)
    return {k: base.stats(base.independent(v, horizon), horizon) for k,v in sorted(buckets.items())}


def bucket_diagnostics(train, hold, all_rows):
    factors = ['direction','obstacle','relative_strength','volume_bin','shadow_score_bin','direction_x_obstacle','direction_x_rs','direction_x_volume','score_x_obstacle']
    report = {}
    stable_harmful = []
    stable_positive = []
    for factor in factors:
        report[factor] = {}
        for h in (3,12,24):
            full = grouped(all_rows, factor, h)
            tr = grouped(train, factor, h)
            ho = grouped(hold, factor, h)
            keys = sorted(set(full)|set(tr)|set(ho))
            rows_out = {}
            for k in keys:
                f = full.get(k, {'n':0,'mean_pct':None,'win_rate_pct':None})
                a = tr.get(k, {'n':0,'mean_pct':None,'win_rate_pct':None})
                b = ho.get(k, {'n':0,'mean_pct':None,'win_rate_pct':None})
                stable_bad = bool(
                    h in (12,24) and a.get('n',0) >= 3 and b.get('n',0) >= 3
                    and a.get('mean_pct') is not None and b.get('mean_pct') is not None
                    and a['mean_pct'] < 0 and b['mean_pct'] < 0
                    and (a.get('win_rate_pct') or 0) < 50 and (b.get('win_rate_pct') or 0) < 50
                )
                stable_good = bool(
                    h in (12,24) and a.get('n',0) >= 3 and b.get('n',0) >= 3
                    and a.get('mean_pct') is not None and b.get('mean_pct') is not None
                    and a['mean_pct'] > 0 and b['mean_pct'] > 0
                    and (a.get('win_rate_pct') or 0) >= 50 and (b.get('win_rate_pct') or 0) >= 50
                )
                rows_out[k] = {'full':f,'train':a,'holdout':b,'stable_harmful':stable_bad,'stable_positive':stable_good}
                if stable_bad:
                    stable_harmful.append({'factor':factor,'bucket':k,'horizon_h':h,'full':f,'train':a,'holdout':b})
                if stable_good:
                    stable_positive.append({'factor':factor,'bucket':k,'horizon_h':h,'full':f,'train':a,'holdout':b})
            report[factor][f'{h}h'] = rows_out
    stable_harmful.sort(key=lambda x: ((x['full'].get('mean_pct') or 0), -(x['full'].get('n') or 0)))
    stable_positive.sort(key=lambda x: (-(x['full'].get('mean_pct') or 0), -(x['full'].get('n') or 0)))
    return report, stable_harmful, stable_positive


def run(path=base.SRC):
    snapshots = base.load_snapshots(path)
    prices = base.build_price_series(snapshots)
    rows, excluded = base.flatten(snapshots)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    retained = [r for r in hourly if fourth.candidate_score(r) >= base.THRESHOLD]
    train, hold, cutoff = split(retained)
    factors, harmful, positive = bucket_diagnostics(train, hold, retained)
    overall = {f'{h}h':base.stats(base.independent(retained,h),h) for h in base.HORIZONS}
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'V6_ROWS_RETAINED_BY_FOURTH_VOTE_DEMOTION_SHADOW',
        'coverage': {'snapshots':len(snapshots),'hourly_v6_rows':len(hourly),'retained_shadow_hours':len(retained),'train_rows':len(train),'holdout_rows':len(hold),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'overall_retained_outcomes': overall,
        'stable_harmful_buckets': harmful,
        'stable_positive_buckets': positive,
        'factor_tables': factors,
        'diagnostic_decision': 'INVESTIGATE_TOP_STABLE_HARMFUL_BUCKET' if harmful else 'NO_STABLE_SINGLE_BUCKET_FOUND',
        'production_change_recommended': False,
        'guardrails': {'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'auto_promotion_enabled':False,'live_execution':False},
        'next_decision': 'Only a stable harmful bucket with adequate independent train and holdout evidence may seed one isolated counterfactual shadow. Do not stack multiple fixes.',
    }


def main():
    r=run()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'coverage':r['coverage'],'overall':r['overall_retained_outcomes'],'stable_harmful_buckets':r['stable_harmful_buckets'][:8],'stable_positive_buckets':r['stable_positive_buckets'][:5],'diagnostic_decision':r['diagnostic_decision'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__':
    main()
