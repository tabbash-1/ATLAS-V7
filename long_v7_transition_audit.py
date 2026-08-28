#!/usr/bin/env python3
"""ATLAS LONG V7 transition-representation audit.

Tests whether *changes* in raw market state before a LONG observation are more
stable predictors of the next 12h return than a static snapshot.

Only historical observations already present in Production snapshots are used.
For every current LONG row we look backward only, selecting the nearest prior
observation for the same symbol inside pre-registered age windows:
  - 1h lane: prior age in [0.5h, 1.5h]
  - 3h lane: prior age in [2.0h, 4.0h]

No future observation is used to construct features. Mature independent 12h
LONG episodes are built once on the full enriched history, then split 60/40.
Research-only: Production scoring, threshold and execution are untouched.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_v7_raw_representation_audit as raw
import long_v7_fixed_episode_split as fixed
import long_v7_train_fitted_ranker as rankutil

OUT = Path('status/long-v7-transition-audit.json')
SCHEMA = 'ATLAS_LONG_V7_TRANSITION_AUDIT_V1_FIXED_EPISODES'
H = 12

STATIC_FIELDS = (
    'momentum_24h_pct',
    'rsi14',
    'price_extension_atr',
    'paced_relative_volume',
    'ema20_vs_ema50_pct',
    'price_vs_ema20_pct',
    'atr_pct',
)
LAGS = {
    '1h': (0.5, 1.5),
    '3h': (2.0, 4.0),
}
FEATURES = tuple(
    f'delta_{field}_{lag}' for lag in LAGS for field in STATIC_FIELDS
)


def fnum(v, default=None):
    return base.fnum(v, default)


def dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if not v:
        return None
    s = str(v).replace('Z', '+00:00')
    try:
        x = datetime.fromisoformat(s)
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def nearest_prior(history, now, min_h, max_h):
    """Return closest prior row whose age is inside the pre-registered window."""
    best = None
    best_age = None
    for r in reversed(history):
        t = dt(r.get('captured_at'))
        if t is None or t >= now:
            continue
        age = (now - t).total_seconds() / 3600.0
        if age < min_h:
            continue
        if age > max_h:
            break
        if best is None or age < best_age:
            best, best_age = r, age
    return best, best_age


def add_transitions(hourly):
    ordered = sorted(
        hourly,
        key=lambda r: (dt(r.get('captured_at')) or datetime.min.replace(tzinfo=timezone.utc), str(r.get('symbol'))),
    )
    histories = defaultdict(list)
    out = []
    for r in ordered:
        sym = r.get('symbol')
        now = dt(r.get('captured_at'))
        if not sym or now is None:
            continue
        x = dict(r)
        lag_ages = {}
        complete_lags = []
        for lag, (lo, hi) in LAGS.items():
            prior, age = nearest_prior(histories[sym], now, lo, hi)
            lag_ages[lag] = None if age is None else round(age, 4)
            if prior is None:
                continue
            ok = True
            for field in STATIC_FIELDS:
                cur = fnum(r.get(field))
                old = fnum(prior.get(field))
                if cur is None or old is None:
                    ok = False
                    break
                x[f'delta_{field}_{lag}'] = cur - old
            if ok:
                complete_lags.append(lag)
        x['transition_lag_ages_h'] = lag_ages
        x['transition_complete_lags'] = complete_lags
        out.append(x)
        histories[sym].append(r)
    return out


def feature_stats(rows, feature):
    pairs = [(fnum(r.get(feature)), fnum(r.get('return_12h_pct'))) for r in rows]
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    if len(pairs) < 3:
        return {'n': len(pairs), 'spearman': None}
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    rho = rankutil._spearman(xs, ys)
    winners = [x for x, y in pairs if y > 0]
    losers = [x for x, y in pairs if y <= 0]
    return {
        'n': len(pairs),
        'spearman': None if rho is None else round(rho, 6),
        'winner_mean': None if not winners else round(sum(winners) / len(winners), 6),
        'loser_mean': None if not losers else round(sum(losers) / len(losers), 6),
        'winner_n': len(winners),
        'loser_n': len(losers),
    }


def lane(eps):
    return {
        'episode_n': len(eps),
        'outcomes': base.stats(eps, H),
        'features': {f: feature_stats(eps, f) for f in FEATURES},
    }


def loo(full_eps):
    syms = sorted({r.get('symbol') for r in full_eps if r.get('symbol')})
    out = {}
    for f in FEATURES:
        tests = []
        for sym in syms:
            st = feature_stats([r for r in full_eps if r.get('symbol') != sym], f)
            tests.append({'left_out_symbol': sym, 'n': st['n'], 'spearman': st['spearman']})
        finite = [x for x in tests if x['spearman'] is not None]
        pos = sum(1 for x in finite if x['spearman'] > 0)
        neg = sum(1 for x in finite if x['spearman'] < 0)
        out[f] = {
            'eligible_tests': len(finite),
            'positive_tests': pos,
            'negative_tests': neg,
            'all_positive': bool(finite) and pos == len(finite),
            'all_negative': bool(finite) and neg == len(finite),
            'tests': tests,
        }
    return out


def run(path=base.SRC):
    snaps, hourly = raw.load_rows(path)
    transitioned = add_transitions(hourly)
    # Episodes are built once from the full transitioned history. Rows may have
    # one lag available and not the other; per-feature n is reported explicitly.
    full_eps = fixed.full_fixed_episodes(transitioned)
    train_eps, holdout_eps, cutoff = fixed.split_fixed_60_40(full_eps)
    if len(train_eps) + len(holdout_eps) != len(full_eps):
        raise AssertionError('fixed split invariant violated')
    lanes = {'full': lane(full_eps), 'train': lane(train_eps), 'holdout': lane(holdout_eps)}
    cross = loo(full_eps)

    stable_pos, stable_neg = [], []
    for f in FEATURES:
        tr = lanes['train']['features'][f]
        ho = lanes['holdout']['features'][f]
        if tr['n'] < 3 or ho['n'] < 3 or tr['spearman'] is None or ho['spearman'] is None:
            continue
        if tr['spearman'] > 0 and ho['spearman'] > 0 and cross[f]['all_positive']:
            stable_pos.append(f)
        if tr['spearman'] < 0 and ho['spearman'] < 0 and cross[f]['all_negative']:
            stable_neg.append(f)

    coverage_by_lag = {}
    for lag in LAGS:
        coverage_by_lag[lag] = {
            'hourly_rows': sum(1 for r in transitioned if lag in r.get('transition_complete_lags', [])),
            'full_episode_rows': sum(1 for r in full_eps if lag in r.get('transition_complete_lags', [])),
            'train_episode_rows': sum(1 for r in train_eps if lag in r.get('transition_complete_lags', [])),
            'holdout_episode_rows': sum(1 for r in holdout_eps if lag in r.get('transition_complete_lags', [])),
        }

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Test whether pre-entry indicator transitions carry stable LONG quality signal using only already-collected historical snapshots.',
        'coverage': {
            'snapshots': len(snaps),
            'hourly_long_rows': len(hourly),
            'full_episode_n': len(full_eps),
            'train_episode_n': len(train_eps),
            'holdout_episode_n': len(holdout_eps),
            'train_plus_holdout_equals_full': len(train_eps) + len(holdout_eps) == len(full_eps),
            'cutoff_at': cutoff.isoformat() if hasattr(cutoff, 'isoformat') else (str(cutoff) if cutoff else None),
            'transition_coverage': coverage_by_lag,
        },
        'pre_registered_lag_windows_hours': {k: list(v) for k, v in LAGS.items()},
        'feature_definition': 'delta = current raw feature minus nearest strictly-prior same-symbol observation inside the lag window',
        'lanes': lanes,
        'leave_one_symbol_out_full': cross,
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
            'future_feature_leakage_allowed': False,
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
