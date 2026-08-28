#!/usr/bin/env python3
"""Canonical fixed-episode chronology for ATLAS LONG V7 research.

Correct order of operations:
1. settle outcomes on the full hourly history;
2. filter to mature LONG rows;
3. de-correlate into independent 12h episodes ONCE on the full history;
4. split those fixed episodes chronologically 60/40.

This prevents a boundary episode from being independently re-anchored on both
sides of the Train/Holdout cutoff. Invariant: train_n + holdout_n == full_n.
"""
from __future__ import annotations

import qualified_false_confidence_audit as base

H = 12


def full_fixed_episodes(hourly_rows):
    mature = [r for r in hourly_rows if r.get('direction') == 'LONG' and r.get('return_12h_pct') is not None]
    return base.independent(mature, H)


def split_fixed_60_40(episodes):
    eps = sorted(episodes, key=lambda r: r.get('captured_at'))
    if not eps:
        return [], [], None
    cut = max(1, min(len(eps)-1, int(len(eps) * 0.60))) if len(eps) > 1 else 1
    train = eps[:cut]
    holdout = eps[cut:]
    cutoff = holdout[0].get('captured_at') if holdout else None
    if len(train) + len(holdout) != len(eps):
        raise AssertionError('fixed episode split invariant violated')
    train_keys = {(r.get('symbol'), str(r.get('captured_at'))) for r in train}
    holdout_keys = {(r.get('symbol'), str(r.get('captured_at'))) for r in holdout}
    if train_keys & holdout_keys:
        raise AssertionError('train/holdout episode overlap detected')
    return train, holdout, cutoff
