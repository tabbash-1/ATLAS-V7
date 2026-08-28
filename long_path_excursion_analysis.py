#!/usr/bin/env python3
"""Path-based diagnosis for accepted combined-shadow LONG setups.

Uses only the hourly price series already embedded in production snapshot history.
For each independent LONG episode at 12h, reconstructs the observed path from
entry to +12h and measures MFE, MAE, time-to-MFE, time-to-MAE, first-3h move,
and giveback from MFE to the 12h result.

Purpose: distinguish bad setup selection from poor entry timing. This is
research-only and never changes Production, threshold 68, or execution.
"""
from __future__ import annotations

import bisect
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as combined
import counterfactual_episode_evaluation as paired

OUT = Path('status/long-path-excursion-analysis.json')
SCHEMA = 'ATLAS_V6_LONG_PATH_EXCURSION_ANALYSIS_V1'
H = 12


def combined_long(r):
    return r.get('direction') == 'LONG' and combined.candidate_qualified(r)


def path_points(series, start, hours=H):
    times = series.get('times') or []
    prices = series.get('prices') or []
    if not times:
        return []
    end = start + timedelta(hours=hours)
    i = bisect.bisect_left(times, start)
    j = bisect.bisect_right(times, end)
    return list(zip(times[i:j], prices[i:j]))


def excursion(r, prices):
    series = prices.get(r['symbol'])
    if not series:
        return None
    entry = base.fnum(r.get('entry'))
    if entry is None or entry <= 0:
        return None
    pts = path_points(series, r['captured_at'], H)
    # Need at least entry-near observation + meaningful later path.
    if len(pts) < 4:
        return None
    path = []
    for ts, px in pts:
        ret = (px / entry - 1.0) * 100.0
        path.append((ts, ret))
    mfe_ts, mfe = max(path, key=lambda x: x[1])
    mae_ts, mae = min(path, key=lambda x: x[1])
    first3 = [x for x in path if x[0] <= r['captured_at'] + timedelta(hours=3)]
    move3 = first3[-1][1] if first3 else None
    ret12 = base.fnum(r.get('return_12h_pct'))
    if ret12 is None:
        return None
    return {
        'captured_at': r['captured_at'].isoformat(),
        'symbol': r['symbol'],
        'entry': entry,
        'score': r.get('corrected_score'),
        'rs_reason': r.get('rs_reason'),
        'obstacle_reason': r.get('obstacle_reason'),
        'relative_volume_replayed': r.get('relative_volume_replayed'),
        'return_12h_pct': round(ret12, 4),
        'mfe_12h_pct': round(mfe, 4),
        'mae_12h_pct': round(mae, 4),
        'time_to_mfe_h': round((mfe_ts-r['captured_at']).total_seconds()/3600.0, 3),
        'time_to_mae_h': round((mae_ts-r['captured_at']).total_seconds()/3600.0, 3),
        'first_3h_move_pct': None if move3 is None else round(move3, 4),
        'giveback_from_mfe_to_12h_pct': round(mfe-ret12, 4),
        'path_points': len(path),
        'winner_12h': ret12 > 0,
        'ever_positive_0_12h': mfe > 0,
        'early_adverse_3h': move3 is not None and move3 < 0,
    }


def avg(vals):
    vals=[v for v in vals if v is not None]
    return None if not vals else round(statistics.mean(vals),4)


def med(vals):
    vals=[v for v in vals if v is not None]
    return None if not vals else round(statistics.median(vals),4)


def summarize(items):
    if not items:
        return {'n':0}
    winners=[x for x in items if x['winner_12h']]
    losers=[x for x in items if not x['winner_12h']]
    positive_then_lose=[x for x in losers if x['ever_positive_0_12h']]
    early_adverse=[x for x in items if x['early_adverse_3h']]
    return {
        'n':len(items),
        'winners_n':len(winners),'losers_n':len(losers),
        'win_rate_pct':round(100*len(winners)/len(items),2),
        'mean_return_12h_pct':avg([x['return_12h_pct'] for x in items]),
        'mean_mfe_12h_pct':avg([x['mfe_12h_pct'] for x in items]),
        'median_mfe_12h_pct':med([x['mfe_12h_pct'] for x in items]),
        'mean_mae_12h_pct':avg([x['mae_12h_pct'] for x in items]),
        'median_mae_12h_pct':med([x['mae_12h_pct'] for x in items]),
        'mean_time_to_mfe_h':avg([x['time_to_mfe_h'] for x in items]),
        'mean_time_to_mae_h':avg([x['time_to_mae_h'] for x in items]),
        'mean_first_3h_move_pct':avg([x['first_3h_move_pct'] for x in items]),
        'mean_giveback_from_mfe_pct':avg([x['giveback_from_mfe_to_12h_pct'] for x in items]),
        'losers_that_were_positive_intraperiod_n':len(positive_then_lose),
        'losers_that_were_positive_intraperiod_pct':None if not losers else round(100*len(positive_then_lose)/len(losers),2),
        'early_adverse_3h_n':len(early_adverse),
        'early_adverse_3h_pct':round(100*len(early_adverse)/len(items),2),
        'winner_profile': {
            'n':len(winners),
            'mean_mfe_pct':avg([x['mfe_12h_pct'] for x in winners]),
            'mean_mae_pct':avg([x['mae_12h_pct'] for x in winners]),
            'mean_first_3h_move_pct':avg([x['first_3h_move_pct'] for x in winners]),
            'mean_time_to_mfe_h':avg([x['time_to_mfe_h'] for x in winners]),
        },
        'loser_profile': {
            'n':len(losers),
            'mean_mfe_pct':avg([x['mfe_12h_pct'] for x in losers]),
            'mean_mae_pct':avg([x['mae_12h_pct'] for x in losers]),
            'mean_first_3h_move_pct':avg([x['first_3h_move_pct'] for x in losers]),
            'mean_time_to_mae_h':avg([x['time_to_mae_h'] for x in losers]),
        },
    }


def diagnosis(summary):
    if summary.get('n',0) < 8:
        return 'PATH_SAMPLE_SMALL_DIAGNOSTIC_ONLY', 'Keep this descriptive; do not create an entry/exit rule from path data yet.'
    losers=summary.get('losers_n',0)
    pos_then=summary.get('losers_that_were_positive_intraperiod_pct')
    wm=summary.get('winner_profile',{}).get('mean_first_3h_move_pct')
    lm=summary.get('loser_profile',{}).get('mean_first_3h_move_pct')
    loser_mfe=summary.get('loser_profile',{}).get('mean_mfe_pct')
    if losers and pos_then is not None and pos_then >= 60 and loser_mfe is not None and loser_mfe > 0.5:
        return 'LONG_PATH_SHOWS_MATERIAL_GIVEBACK', 'Test a research-only path/exit overlay; do not add another entry veto.'
    if wm is not None and lm is not None and wm > 0 and lm < 0:
        return 'EARLY_PATH_SEPARATES_LONG_WINNERS_AND_LOSERS', 'Test one research-only early-confirmation entry overlay with paired dynamic/fixed evaluation.'
    if loser_mfe is not None and loser_mfe <= 0.25:
        return 'LONG_LOSERS_RARELY_DEVELOP_FAVORABLE_EXCURSION', 'Entry selection/regime representation is the dominant issue; inspect existing historical regime/path features rather than exit timing.'
    return 'LONG_PATH_MIXED_NO_SINGLE_TIMING_RULE', 'Do not add another veto. Continue representation diagnostics with historically available regime/path features.'


def run(path=base.SRC):
    snaps=base.load_snapshots(path); prices=base.build_price_series(snaps)
    rows,excluded=base.flatten(snaps); base.settle(rows,prices); hourly=base.hourly_dedupe(rows)
    pool=[r for r in hourly if combined_long(r)]
    episodes=base.independent(pool,H)
    items=[x for x in (excursion(r,prices) for r in episodes) if x]
    # Time split AFTER fixing independent episode anchors, avoiding substitution.
    episode_by_id={(x['symbol'],x['captured_at']):x for x in items}
    train_rows,hold_rows,cutoff=paired.split_60_40(episodes)
    train_keys={(r['symbol'],r['captured_at'].isoformat()) for r in train_rows}
    hold_keys={(r['symbol'],r['captured_at'].isoformat()) for r in hold_rows}
    train=[x for k,x in episode_by_id.items() if k in train_keys]
    hold=[x for k,x in episode_by_id.items() if k in hold_keys]
    full_summary=summarize(items); d,next_step=diagnosis(full_summary)
    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'ACCEPTED_COMBINED_SHADOW_LONG_FIXED_12H_EPISODES',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'combined_long_pool_hours':len(pool),'independent_long_12h_episodes':len(episodes),'episodes_with_path':len(items),'train_path_episodes':len(train),'holdout_path_episodes':len(hold),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'full':full_summary,'train':summarize(train),'holdout':summarize(hold),
        'episodes':items,
        'diagnosis':d,'next_step':next_step,
        'production_change_recommended':False,
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'combined_shadow_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'coverage':r['coverage'],'full':r['full'],'train':r['train'],'holdout':r['holdout'],'diagnosis':r['diagnosis'],'next_step':r['next_step'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__': main()
