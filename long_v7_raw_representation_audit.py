#!/usr/bin/env python3
"""ATLAS LONG V7 raw-market representation audit (fixed-episode V2).

Uses only historical Production snapshots already in the repository. It enriches
V6 LONG observations with raw indicators present on every historical LONG row:
EMA20, EMA50, RSI14, ATR14, 24h momentum and volume ratio.

Method correction in V2: mature independent 12h LONG episodes are built ONCE on
the full history, then those fixed episodes are split chronologically 60/40.
This guarantees Train + Holdout == Full and prevents boundary re-anchoring.

Feature transforms are pre-specified market-structure quantities rather than a
parameter sweep. Pre-fix volume is normalized through the same historical paced
RV replay already used by ATLAS audits.

Research-only; no Production score, threshold or execution path is modified.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_v7_train_fitted_ranker as rankutil
import long_v7_fixed_episode_split as fixed

OUT = Path('status/long-v7-raw-representation-audit.json')
SCHEMA = 'ATLAS_LONG_V7_RAW_REPRESENTATION_AUDIT_V2_FIXED_EPISODES'
H = 12
FEATURES = (
    'price_vs_ema20_pct',
    'ema20_vs_ema50_pct',
    'price_extension_atr',
    'rsi14',
    'momentum_24h_pct',
    'atr_pct',
    'paced_relative_volume',
)


def fnum(v, default=None):
    return base.fnum(v, default)


def enrich_row(ts, symbol, d):
    r = base.replay_observation(ts, symbol, d)
    if r is None or r.get('excluded') or r.get('direction') != 'LONG':
        return None
    ind = d.get('indicators') or {}
    px = fnum(r.get('entry'))
    ema20 = fnum(ind.get('ema20'))
    ema50 = fnum(ind.get('ema50'))
    rsi = fnum(ind.get('rsi14'))
    atr = fnum(ind.get('atr14'))
    mom = fnum(ind.get('momentum_24h_pct'))
    rv = fnum(r.get('relative_volume_replayed'))
    if rv is None:
        rv = fnum(ind.get('volume_ratio'))
    if None in (px, ema20, ema50, rsi, atr, mom, rv) or px <= 0 or ema20 <= 0 or ema50 <= 0 or atr <= 0:
        return None
    r = dict(r)
    r.update({
        'price_vs_ema20_pct': (px / ema20 - 1.0) * 100.0,
        'ema20_vs_ema50_pct': (ema20 / ema50 - 1.0) * 100.0,
        'price_extension_atr': (px - ema20) / atr,
        'rsi14': rsi,
        'momentum_24h_pct': mom,
        'atr_pct': atr / px * 100.0,
        'paced_relative_volume': rv,
    })
    return r


def load_rows(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows = []
    for ts, snap in snaps:
        for symbol, d in (snap.get('decisions') or {}).items():
            x = enrich_row(ts, symbol, d or {})
            if x is not None:
                rows.append(x)
    base.settle(rows, prices)
    return snaps, base.hourly_dedupe(rows)


def mature_episodes(rows):
    return fixed.full_fixed_episodes(rows)


def feature_stats(rows, feature):
    pairs = [(fnum(r.get(feature)), fnum(r.get('return_12h_pct'))) for r in rows]
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    if len(xs) < 3:
        return {'n': len(xs), 'spearman': None}
    rho = rankutil._spearman(xs, ys)
    winners = [x for x, y in pairs if y > 0]
    losers = [x for x, y in pairs if y <= 0]
    return {
        'n': len(xs),
        'spearman': None if rho is None else round(rho, 6),
        'winner_mean': None if not winners else round(sum(winners) / len(winners), 6),
        'loser_mean': None if not losers else round(sum(losers) / len(losers), 6),
        'winner_n': len(winners),
        'loser_n': len(losers),
    }


def lane_eps(eps):
    return {
        'episode_n': len(eps),
        'features': {f: feature_stats(eps, f) for f in FEATURES},
        'outcomes': base.stats(eps, H),
    }


def leave_one_symbol_out(eps):
    syms = sorted({r.get('symbol') for r in eps if r.get('symbol')})
    out = {}
    for f in FEATURES:
        tests = []
        for sym in syms:
            sub = [r for r in eps if r.get('symbol') != sym]
            st = feature_stats(sub, f)
            tests.append({'left_out_symbol': sym, 'n': st['n'], 'spearman': st['spearman']})
        finite = [x for x in tests if x['spearman'] is not None]
        pos = sum(1 for x in finite if x['spearman'] > 0)
        neg = sum(1 for x in finite if x['spearman'] < 0)
        out[f] = {
            'tests': tests,
            'eligible_tests': len(finite),
            'positive_tests': pos,
            'negative_tests': neg,
            'all_positive': bool(finite) and pos == len(finite),
            'all_negative': bool(finite) and neg == len(finite),
        }
    return out


def run(path=base.SRC):
    snaps, hourly = load_rows(path)
    full_eps = fixed.full_fixed_episodes(hourly)
    train_eps, holdout_eps, cutoff = fixed.split_fixed_60_40(full_eps)
    if len(train_eps) + len(holdout_eps) != len(full_eps):
        raise AssertionError('fixed split count invariant violated')
    lanes = {
        'full': lane_eps(full_eps),
        'train': lane_eps(train_eps),
        'holdout': lane_eps(holdout_eps),
    }
    loo = leave_one_symbol_out(full_eps)

    stable_pos = []
    stable_neg = []
    for f in FEATURES:
        tr = lanes['train']['features'][f]['spearman']
        ho = lanes['holdout']['features'][f]['spearman']
        if tr is None or ho is None:
            continue
        if tr > 0 and ho > 0 and loo[f]['all_positive']:
            stable_pos.append(f)
        if tr < 0 and ho < 0 and loo[f]['all_negative']:
            stable_neg.append(f)

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'Determine whether raw market-state representation carries stable LONG quality signal missing from the V6 aggregate score, using fixed independent episodes.',
        'coverage': {
            'snapshots': len(snaps),
            'hourly_v6_long_rows_with_raw_features': len(hourly),
            'cutoff_at': cutoff.isoformat() if hasattr(cutoff, 'isoformat') else (str(cutoff) if cutoff else None),
            'full_mature_independent_12h_episodes': len(full_eps),
            'train_mature_independent_12h_episodes': len(train_eps),
            'holdout_mature_independent_12h_episodes': len(holdout_eps),
            'train_plus_holdout_equals_full': len(train_eps) + len(holdout_eps) == len(full_eps),
            'episode_split_order': 'FULL_DECORELATE_THEN_SPLIT',
        },
        'feature_definitions': {
            'price_vs_ema20_pct': '(entry / ema20 - 1) * 100',
            'ema20_vs_ema50_pct': '(ema20 / ema50 - 1) * 100',
            'price_extension_atr': '(entry - ema20) / atr14',
            'rsi14': 'stored raw RSI14',
            'momentum_24h_pct': 'stored raw 24h momentum',
            'atr_pct': 'atr14 / entry * 100',
            'paced_relative_volume': 'historically replayed partial-hour-safe relative volume',
        },
        'lanes': lanes,
        'leave_one_symbol_out_full': loo,
        'stable_positive_raw_predictors': stable_pos,
        'stable_negative_raw_predictors': stable_neg,
        'research_decision': 'RAW_REPRESENTATION_HAS_STABLE_SIGNAL' if stable_pos or stable_neg else 'RAW_REPRESENTATION_NOT_YET_STABLE',
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
        'stable_positive_raw_predictors': out['stable_positive_raw_predictors'],
        'stable_negative_raw_predictors': out['stable_negative_raw_predictors'],
        'lanes': out['lanes'],
        'research_decision': out['research_decision'],
        'guardrails': out['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
