#!/usr/bin/env python3
"""ATLAS LONG V7 transition-representation audit.

Tests whether HOW raw indicators changed before a LONG observation contains
stable 12h quality signal missing from the static V6 snapshot.

Only historical Production snapshots already stored in the repository are used.
For each V6 LONG hourly observation, prior same-symbol market states are located
strictly before the decision time at approximately 1h and 3h lags. No future
information enters any feature.

Independent mature 12h episodes are built once on the full history, then split
chronologically 60/40 via the canonical fixed-episode helper.

Research-only: no Production score, threshold, decision gate or execution path
is changed.
"""
from __future__ import annotations

import bisect
import json
from collections import defaultdict
from datetime import timedelta, timezone, datetime
from pathlib import Path

import qualified_false_confidence_audit as base
import long_v7_raw_representation_audit as raw
import long_v7_train_fitted_ranker as rankutil
import long_v7_fixed_episode_split as fixed

OUT = Path('status/long-v7-transition-representation-audit.json')
SCHEMA = 'ATLAS_LONG_V7_TRANSITION_REPRESENTATION_AUDIT_V1_FIXED_EPISODES'
H = 12

LAG_RULES = {
    '1h': (60, 35),
    '3h': (180, 75),
}

BASE_STATE_FEATURES = (
    'rsi14',
    'momentum_24h_pct',
    'ema_spread_pct',
    'atr_over_ema20_pct',
    'paced_relative_volume',
)

FEATURES = tuple(
    f'delta_{feature}_{lag}'
    for lag in ('1h', '3h')
    for feature in BASE_STATE_FEATURES
) + ('ema20_change_pct_1h', 'ema20_change_pct_3h')


def fnum(v, default=None):
    return base.fnum(v, default)


def state_from_decision(ts, symbol, decision):
    ind = (decision or {}).get('indicators') or {}
    ema20 = fnum(ind.get('ema20'))
    ema50 = fnum(ind.get('ema50'))
    rsi = fnum(ind.get('rsi14'))
    atr = fnum(ind.get('atr14'))
    mom = fnum(ind.get('momentum_24h_pct'))
    rv_raw = fnum(ind.get('volume_ratio'))
    if None in (ema20, ema50, rsi, atr, mom, rv_raw):
        return None
    if ema20 <= 0 or ema50 <= 0 or atr <= 0:
        return None
    return {
        'ts': ts,
        'symbol': symbol,
        'rsi14': rsi,
        'momentum_24h_pct': mom,
        'ema20': ema20,
        'ema_spread_pct': (ema20 / ema50 - 1.0) * 100.0,
        'atr_over_ema20_pct': atr / ema20 * 100.0,
        'paced_relative_volume': base.paced_rv(rv_raw, base.progress_from_timestamp(ts)),
    }


def build_state_index(snaps):
    by_symbol = defaultdict(list)
    exact = {}
    for ts, snap in snaps:
        for symbol, d in (snap.get('decisions') or {}).items():
            st = state_from_decision(ts, symbol, d)
            if st is None:
                continue
            by_symbol[symbol].append(st)
            exact[(symbol, ts)] = st
    times = {}
    for symbol, rows in by_symbol.items():
        rows.sort(key=lambda x: x['ts'])
        times[symbol] = [x['ts'] for x in rows]
    return by_symbol, times, exact


def nearest_prior(rows, times, target_ts, lag_minutes, tolerance_minutes):
    desired = target_ts - timedelta(minutes=lag_minutes)
    lo = desired - timedelta(minutes=tolerance_minutes)
    hi = desired + timedelta(minutes=tolerance_minutes)
    # Prior state must always be strictly before target_ts.
    hi = min(hi, target_ts - timedelta(seconds=1))
    idx = bisect.bisect_right(times, hi) - 1
    if idx < 0:
        return None
    candidate = rows[idx]
    if candidate['ts'] < lo or candidate['ts'] >= target_ts:
        return None
    return candidate


def transition_features(current, prior, lag):
    out = {}
    for feature in BASE_STATE_FEATURES:
        a = fnum(current.get(feature))
        b = fnum(prior.get(feature))
        if a is not None and b is not None:
            out[f'delta_{feature}_{lag}'] = a - b
    cur_ema = fnum(current.get('ema20'))
    prev_ema = fnum(prior.get('ema20'))
    if cur_ema is not None and prev_ema is not None and prev_ema > 0:
        out[f'ema20_change_pct_{lag}'] = (cur_ema / prev_ema - 1.0) * 100.0
    return out


def enrich_transitions(hourly_rows, by_symbol, times, exact):
    out = []
    for r in hourly_rows:
        symbol = r.get('symbol')
        ts = base.parse_time(r.get('captured_at'))
        if not symbol or ts is None or symbol not in by_symbol:
            out.append(dict(r))
            continue
        current = exact.get((symbol, ts))
        if current is None:
            # Hourly de-dupe rows originate from a snapshot timestamp; this is a
            # conservative fallback to the nearest state at or before that time.
            idx = bisect.bisect_right(times[symbol], ts) - 1
            current = by_symbol[symbol][idx] if idx >= 0 and by_symbol[symbol][idx]['ts'] == ts else None
        x = dict(r)
        if current is not None:
            for lag, (minutes, tolerance) in LAG_RULES.items():
                prior = nearest_prior(by_symbol[symbol], times[symbol], ts, minutes, tolerance)
                if prior is not None:
                    x.update(transition_features(current, prior, lag))
        out.append(x)
    return out


def feature_stats(rows, feature):
    pairs = [(fnum(r.get(feature)), fnum(r.get('return_12h_pct'))) for r in rows]
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    if len(xs) < 3:
        return {'n': len(xs), 'coverage_pct': round(len(xs) / max(1, len(rows)) * 100.0, 2), 'spearman': None}
    rho = rankutil._spearman(xs, ys)
    winners = [x for x, y in pairs if y > 0]
    losers = [x for x, y in pairs if y <= 0]
    return {
        'n': len(xs),
        'coverage_pct': round(len(xs) / max(1, len(rows)) * 100.0, 2),
        'spearman': None if rho is None else round(rho, 6),
        'winner_mean': None if not winners else round(sum(winners) / len(winners), 6),
        'loser_mean': None if not losers else round(sum(losers) / len(losers), 6),
        'winner_n': len(winners),
        'loser_n': len(losers),
    }


def lane(eps):
    return {
        'episode_n': len(eps),
        'features': {f: feature_stats(eps, f) for f in FEATURES},
        'outcomes': base.stats(eps, H),
    }


def leave_one_symbol_out(eps):
    symbols = sorted({r.get('symbol') for r in eps if r.get('symbol')})
    result = {}
    for feature in FEATURES:
        tests = []
        for sym in symbols:
            st = feature_stats([r for r in eps if r.get('symbol') != sym], feature)
            tests.append({'left_out_symbol': sym, 'n': st['n'], 'spearman': st['spearman']})
        eligible = [x for x in tests if x['spearman'] is not None]
        pos = sum(1 for x in eligible if x['spearman'] > 0)
        neg = sum(1 for x in eligible if x['spearman'] < 0)
        result[feature] = {
            'tests': tests,
            'eligible_tests': len(eligible),
            'positive_tests': pos,
            'negative_tests': neg,
            'all_positive': bool(eligible) and pos == len(eligible),
            'all_negative': bool(eligible) and neg == len(eligible),
        }
    return result


def run(path=base.SRC):
    snaps, hourly = raw.load_rows(path)
    by_symbol, times, exact = build_state_index(snaps)
    transitioned = enrich_transitions(hourly, by_symbol, times, exact)
    full_eps = fixed.full_fixed_episodes(transitioned)
    train_eps, holdout_eps, cutoff = fixed.split_fixed_60_40(full_eps)
    if len(train_eps) + len(holdout_eps) != len(full_eps):
        raise AssertionError('fixed episode split count invariant violated')

    lanes = {'full': lane(full_eps), 'train': lane(train_eps), 'holdout': lane(holdout_eps)}
    loo = leave_one_symbol_out(full_eps)
    stable_pos, stable_neg = [], []
    for feature in FEATURES:
        tr = lanes['train']['features'][feature]
        ho = lanes['holdout']['features'][feature]
        # Require usable evidence in both chronological lanes, not merely a sign.
        if tr['n'] < 5 or ho['n'] < 4 or tr['spearman'] is None or ho['spearman'] is None:
            continue
        if tr['spearman'] > 0 and ho['spearman'] > 0 and loo[feature]['all_positive']:
            stable_pos.append(feature)
        if tr['spearman'] < 0 and ho['spearman'] < 0 and loo[feature]['all_negative']:
            stable_neg.append(feature)

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Test whether pre-decision indicator transitions contain stable LONG quality signal beyond static V6 state.',
        'coverage': {
            'snapshots': len(snaps),
            'hourly_v6_long_rows': len(hourly),
            'full_episode_n': len(full_eps),
            'train_episode_n': len(train_eps),
            'holdout_episode_n': len(holdout_eps),
            'train_plus_holdout_equals_full': len(train_eps) + len(holdout_eps) == len(full_eps),
            'cutoff_at': cutoff.isoformat() if hasattr(cutoff, 'isoformat') else (str(cutoff) if cutoff else None),
            'episode_split_order': 'FULL_DECORELATE_THEN_SPLIT',
        },
        'lag_rules': {
            k: {'target_minutes': v[0], 'tolerance_minutes': v[1], 'strictly_prior': True}
            for k, v in LAG_RULES.items()
        },
        'feature_definitions': {
            'delta_*': 'current state minus strictly-prior same-symbol state at the named lag',
            'ema20_change_pct_*': '(current EMA20 / prior EMA20 - 1) * 100',
            'ema_spread_pct': '(EMA20 / EMA50 - 1) * 100',
            'atr_over_ema20_pct': 'ATR14 / EMA20 * 100',
            'paced_relative_volume': 'partial-hour-safe relative volume at each historical timestamp',
        },
        'lanes': lanes,
        'leave_one_symbol_out_full': loo,
        'stable_positive_transition_predictors': stable_pos,
        'stable_negative_transition_predictors': stable_neg,
        'research_decision': 'TRANSITION_REPRESENTATION_HAS_STABLE_SIGNAL' if stable_pos or stable_neg else 'TRANSITION_REPRESENTATION_NOT_YET_STABLE',
        'production_change_recommended': False,
        'guardrails': {
            'research_only': True,
            'production_threshold': base.THRESHOLD,
            'production_threshold_changed': False,
            'production_scoring_changed': False,
            'auto_promotion_enabled': False,
            'can_override_production': False,
            'live_execution': False,
        },
    }


def main():
    out = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'coverage': out['coverage'],
        'stable_positive_transition_predictors': out['stable_positive_transition_predictors'],
        'stable_negative_transition_predictors': out['stable_negative_transition_predictors'],
        'research_decision': out['research_decision'],
        'guardrails': out['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
