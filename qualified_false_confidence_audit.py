#!/usr/bin/env python3
"""Research-only audit of V6 positive score components using existing snapshots.

This replays the known partial-hour volume correction, settles future prices from
status/history/production-snapshots.jsonl itself, then removes exactly one
positive component at a time from replay-qualified (score >= 68) observations.
It does NOT modify Production scoring, threshold, or execution.
"""
from __future__ import annotations

import bisect
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC = Path('status/history/production-snapshots.jsonl')
OUT = Path('status/qualified-false-confidence-audit.json')
SCHEMA = 'ATLAS_V6_QUALIFIED_FALSE_CONFIDENCE_AUDIT_V1'
V6_PREFIX = 'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE'
FIX_TAG = 'PARTIAL_VOLUME_TIME_FIX_V1'
THRESHOLD = 68.0
HORIZONS = (3, 12, 24)
TOLERANCE_MINUTES = 90


def fnum(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def parse_time(v):
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except Exception:
        return None


def progress_from_timestamp(ts):
    if ts is None:
        return 1.0
    sec = ts.minute * 60 + ts.second + ts.microsecond / 1_000_000
    return max(0.10, min(1.0, sec / 3600.0))


def paced_rv(raw_rv, progress):
    return min(4.0, max(0.0, fnum(raw_rv, 0.0)) / max(0.10, min(1.0, fnum(progress, 1.0))))


def volume_bonus(rv):
    return min(10.0, max(0.0, (fnum(rv, 0.0) - 1.0) * 10.0))


def round_score(v):
    return int(round(max(0.0, min(100.0, fnum(v, 0.0)))))


def load_snapshots(path=SRC):
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                x = json.loads(line)
            except Exception:
                continue
            ts = parse_time(x.get('captured_at'))
            if ts:
                rows.append((ts, x))
    return sorted(rows, key=lambda x: x[0])


def build_price_series(snapshots):
    """Every decision's entry is px in production_signal_scoring.py."""
    by_symbol = defaultdict(list)
    for ts, snap in snapshots:
        for symbol, d in (snap.get('decisions') or {}).items():
            px = fnum((d or {}).get('entry'))
            if px is not None and px > 0:
                by_symbol[str(symbol).upper()].append((ts, px))
    # collapse exact duplicate timestamps conservatively
    out = {}
    for symbol, vals in by_symbol.items():
        seen = {}
        for ts, px in vals:
            seen.setdefault(ts, px)
        ordered = sorted(seen.items())
        out[symbol] = {'times': [x[0] for x in ordered], 'prices': [x[1] for x in ordered]}
    return out


def nearest_price(series, target, tolerance_minutes=TOLERANCE_MINUTES):
    times = series.get('times') or []
    prices = series.get('prices') or []
    if not times:
        return None
    i = bisect.bisect_left(times, target)
    candidates = []
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(times):
            delta = abs((times[j] - target).total_seconds()) / 60.0
            if delta <= tolerance_minutes:
                candidates.append((delta, times[j], prices[j]))
    if not candidates:
        return None
    return min(candidates, key=lambda x: (x[0], x[1]))


def replay_observation(ts, symbol, d):
    version = str(d.get('scoring_version') or '')
    direction = str(d.get('candidate_direction') or '').upper()
    score = fnum(d.get('score'))
    entry = fnum(d.get('entry'))
    attr = d.get('score_attribution') or {}
    attr_final = fnum(attr.get('final_score'))
    raw_score = fnum(attr.get('raw_score'))
    if not version.startswith(V6_PREFIX) or direction not in ('LONG', 'SHORT'):
        return None
    if score is None or entry is None or entry <= 0 or raw_score is None or attr_final is None:
        return None
    # Exclude overlays whose decision-level score no longer decomposes to this attribution.
    if abs(score - attr_final) > 0.51:
        return {'excluded': 'ATTRIBUTION_SCORE_MISMATCH'}

    old_vb = fnum(attr.get('volume_bonus'), 0.0) or 0.0
    stored_rv = fnum(d.get('relative_volume'))
    if FIX_TAG in version or stored_rv is None:
        corrected_vb = old_vb
        corrected_rv = stored_rv
        volume_delta = 0.0
    else:
        p = progress_from_timestamp(ts)
        corrected_rv = paced_rv(stored_rv, p)
        corrected_vb = volume_bonus(corrected_rv)
        volume_delta = max(0.0, corrected_vb - old_vb)

    corrected_raw = raw_score + volume_delta
    corrected_score = round_score(corrected_raw)
    votes = int(fnum(d.get('direction_votes'), 0) or 0)
    trend_base = fnum(attr.get('trend_base'), 0.0) or 0.0
    rs = fnum(attr.get('relative_strength_adjustment'), 0.0) or 0.0
    futures = fnum(attr.get('futures_adjustment'), 0.0) or 0.0
    obstacle = fnum(attr.get('obstacle_adjustment'), 0.0) or 0.0

    return {
        'excluded': None,
        'captured_at': ts,
        'symbol': str(symbol).upper(),
        'direction': direction,
        'entry': entry,
        'stored_score': score,
        'corrected_score': corrected_score,
        'scoring_version': version,
        'signal_qualified_stored': bool(d.get('signal_qualified')),
        'direction_votes': votes,
        'trend_base': trend_base,
        'volume_bonus': corrected_vb,
        'stored_volume_bonus': old_vb,
        'volume_fix_delta': volume_delta,
        'relative_volume_replayed': corrected_rv,
        'rs_adjustment': rs,
        'rs_reason': str(attr.get('relative_strength_reason') or 'UNKNOWN'),
        'futures_adjustment': futures,
        'futures_reason': str(attr.get('futures_reason') or 'UNKNOWN'),
        'obstacle_adjustment': obstacle,
        'obstacle_reason': str(attr.get('obstacle_reason') or 'UNKNOWN'),
    }


def flatten(snapshots):
    rows = []
    excluded = defaultdict(int)
    for ts, snap in snapshots:
        for symbol, d in (snap.get('decisions') or {}).items():
            r = replay_observation(ts, symbol, d or {})
            if r is None:
                continue
            if r.get('excluded'):
                excluded[r['excluded']] += 1
                continue
            rows.append(r)
    return rows, dict(excluded)


def settle(rows, prices):
    for r in rows:
        series = prices.get(r['symbol'])
        if not series:
            continue
        for h in HORIZONS:
            target = r['captured_at'] + timedelta(hours=h)
            got = nearest_price(series, target)
            if not got:
                continue
            delta_min, settle_at, future_px = got
            raw_ret = (future_px / r['entry'] - 1.0) * 100.0
            directional = raw_ret if r['direction'] == 'LONG' else -raw_ret
            r[f'return_{h}h_pct'] = directional
            r[f'settle_{h}h_lag_min'] = delta_min
            r[f'settle_{h}h_at'] = settle_at
    return rows


def hourly_dedupe(rows):
    chosen = {}
    for r in sorted(rows, key=lambda x: x['captured_at']):
        key = (r['symbol'], r['direction'], r['captured_at'].replace(minute=0, second=0, microsecond=0))
        chosen.setdefault(key, r)
    return list(chosen.values())


def independent(rows, horizon_h):
    gap = timedelta(hours=horizon_h)
    groups = defaultdict(list)
    for r in rows:
        groups[(r['symbol'], r['direction'])].append(r)
    out = []
    for items in groups.values():
        last = None
        for r in sorted(items, key=lambda x: x['captured_at']):
            if last is None or r['captured_at'] - last >= gap:
                out.append(r)
                last = r['captured_at']
    return sorted(out, key=lambda x: x['captured_at'])


def stats(rows, h):
    vals = [fnum(r.get(f'return_{h}h_pct')) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {'n': 0, 'mean_pct': None, 'median_pct': None, 'win_rate_pct': None}
    return {
        'n': len(vals),
        'mean_pct': round(statistics.mean(vals), 4),
        'median_pct': round(statistics.median(vals), 4),
        'win_rate_pct': round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
    }


def stability_harmful(rows, h):
    usable = independent([r for r in rows if fnum(r.get(f'return_{h}h_pct')) is not None], h)
    if len(usable) < 5:
        return {'n': len(usable), 'eligible': False, 'stable_harmful': False}
    cut = max(1, min(len(usable)-1, int(len(usable) * 0.60)))
    train, hold = usable[:cut], usable[cut:]
    tr, ho = stats(train, h), stats(hold, h)
    symbols = sorted({r['symbol'] for r in usable})
    jk = []
    for s in symbols:
        x = stats([r for r in usable if r['symbol'] != s], h)
        if x['n']:
            jk.append(x)
    neg = sum((x.get('mean_pct') or 0) < 0 for x in jk)
    win_lt50 = sum((x.get('win_rate_pct') or 100) < 50 for x in jk)
    stable = bool(
        len(usable) >= 8
        and (tr.get('mean_pct') or 0) < 0
        and (ho.get('mean_pct') or 0) < 0
        and (ho.get('win_rate_pct') or 100) < 50
        and jk and neg == len(jk) and win_lt50 == len(jk)
    )
    return {
        'n': len(usable), 'eligible': True, 'train': tr, 'holdout': ho,
        'leave_one_symbol_out': {
            'tests': len(jk), 'negative_mean': neg, 'win_rate_lt_50': win_lt50,
            'all_negative_and_win_lt_50': bool(jk and neg == len(jk) and win_lt50 == len(jk)),
        },
        'stable_harmful': stable,
    }


def bonus_delta(r, name):
    if name == 'FOURTH_VOTE_PREMIUM':
        return 4.0 if r['direction_votes'] >= 4 and r['trend_base'] >= 68 else 0.0
    if name == 'VOLUME_BONUS':
        return max(0.0, r['volume_bonus'])
    if name == 'ALIGNED_RELATIVE_STRENGTH_BONUS':
        return max(0.0, r['rs_adjustment'])
    if name == 'ALIGNED_FUTURES_BONUS':
        return max(0.0, r['futures_adjustment'])
    if name == 'CLEAR_STRUCTURE_BONUS':
        return max(0.0, r['obstacle_adjustment'])
    raise KeyError(name)


def evaluate_bonus(qualified, name):
    critical = []
    for r in qualified:
        delta = bonus_delta(r, name)
        if delta <= 0:
            continue
        cf = round_score(r['corrected_score'] - delta)
        if cf < THRESHOLD:
            x = dict(r)
            x['bonus_delta_removed'] = round(delta, 4)
            x['counterfactual_score'] = cf
            critical.append(x)
    horizon = {}
    stable_any = False
    for h in HORIZONS:
        eps = independent(critical, h)
        s = stats(eps, h)
        st = stability_harmful(critical, h)
        horizon[f'{h}h'] = {'outcomes': s, 'stability': st}
        stable_any = stable_any or st.get('stable_harmful', False)
    return {
        'hourly_bonus_critical_qualifications': len(critical),
        'horizons': horizon,
        'research_interpretation': 'SHADOW_DEMOTION_CANDIDATE' if stable_any else 'NO_STABLE_FALSE_CONFIDENCE_EVIDENCE',
        'production_change_recommended': False,
    }


def score_band(score):
    if score <= 71: return '68-71'
    if score <= 75: return '72-75'
    if score <= 79: return '76-79'
    return '80+'


def report_stats(rows):
    return {f'{h}h': stats(independent(rows, h), h) for h in HORIZONS}


def audit(path=SRC):
    snapshots = load_snapshots(path)
    prices = build_price_series(snapshots)
    rows, excluded = flatten(snapshots)
    settle(rows, prices)
    hourly = hourly_dedupe(rows)
    qualified = [r for r in hourly if r['corrected_score'] >= THRESHOLD]
    stored_qualified = [r for r in hourly if r['signal_qualified_stored']]
    volume_recovered = [r for r in qualified if not r['signal_qualified_stored'] and r['volume_fix_delta'] > 0]

    bonuses = (
        'FOURTH_VOTE_PREMIUM', 'VOLUME_BONUS', 'ALIGNED_RELATIVE_STRENGTH_BONUS',
        'ALIGNED_FUTURES_BONUS', 'CLEAR_STRUCTURE_BONUS',
    )
    bonus_results = {name: evaluate_bonus(qualified, name) for name in bonuses}

    bands = defaultdict(list)
    for r in qualified:
        bands[score_band(r['corrected_score'])].append(r)

    by_votes = defaultdict(list)
    for r in qualified:
        by_votes[str(r['direction_votes'])].append(r)

    candidates = [k for k,v in bonus_results.items() if v['research_interpretation'] == 'SHADOW_DEMOTION_CANDIDATE']
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Test whether any single positive V6 score component creates stable false confidence above threshold 68, using only existing Production snapshots.',
        'method': {
            'source': str(path),
            'snapshot_price': 'decision.entry; production_signal_scoring.py stores entry = px',
            'volume_replay': 'pre PARTIAL_VOLUME_TIME_FIX_V1 observations are replayed with paced RV before qualification analysis',
            'settlement': f'nearest same-symbol snapshot to +3h/+12h/+24h within ±{TOLERANCE_MINUTES} minutes',
            'hourly_dedupe': 'earliest symbol/direction observation per UTC hour',
            'outcome_independence': 'minimum gap equals each evaluated horizon (3h/12h/24h)',
            'counterfactual': 'remove exactly one positive bonus; flag only if replay-qualified score falls below 68',
            'stability_gate': 'n>=8 independent observations, negative train and holdout mean, holdout win<50%, and all leave-one-symbol-out tests negative with win<50%',
            'important_limit': 'directional return from snapshot price is not realized trade PnL and does not simulate stop/target path.',
        },
        'coverage': {
            'snapshots': len(snapshots),
            'first_snapshot_at': snapshots[0][0].isoformat() if snapshots else None,
            'last_snapshot_at': snapshots[-1][0].isoformat() if snapshots else None,
            'v6_decomposable_rows': len(rows),
            'hourly_v6_rows': len(hourly),
            'stored_qualified_hours': len(stored_qualified),
            'replay_qualified_hours': len(qualified),
            'volume_fix_recovered_qualified_hours': len(volume_recovered),
            'excluded': excluded,
        },
        'replay_qualified_outcomes': report_stats(qualified),
        'score_bands': {k: {'hourly_rows': len(v), 'outcomes': report_stats(v)} for k,v in sorted(bands.items())},
        'by_direction_votes': {k: {'hourly_rows': len(v), 'outcomes': report_stats(v)} for k,v in sorted(by_votes.items())},
        'single_bonus_counterfactuals': bonus_results,
        'shadow_demotion_candidates': candidates,
        'guardrails': {
            'research_only': True,
            'production_threshold': THRESHOLD,
            'production_threshold_changed': False,
            'production_score_changed': False,
            'auto_promotion_enabled': False,
            'live_execution': False,
        },
        'next_decision': 'Only a single bonus with stable harmful evidence may advance to an isolated demotion shadow. If none qualify, keep Production unchanged and move to predeclared interaction calibration rather than feature fishing.',
    }


def main():
    r = audit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=2, sort_keys=True, default=str) + '\n')
    print(json.dumps({
        'schema': r['schema'], 'coverage': r['coverage'],
        'shadow_demotion_candidates': r['shadow_demotion_candidates'],
        'replay_qualified_outcomes': r['replay_qualified_outcomes'],
        'guardrails': r['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
