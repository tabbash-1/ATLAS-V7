"""Attach 4H/12H price-action context to the canonical ATLAS decision.

This layer is analysis-only. It cannot alter score, threshold, raw qualification,
or enable live execution. It exposes forward-testable context for later evidence
promotion rather than silently changing trading rules.
"""
from __future__ import annotations

from htf_price_action import VERSION as PRICE_ACTION_VERSION, analyze_price_action, combine_price_action
from htf_structural_thesis import _fetch_klines

VERSION = "HTF_PRICE_ACTION_OVERLAY_V1"


def build_live_price_action(atlas, symbol):
    frames = {}
    errors = {}
    for tf in ('4h', '12h'):
        try:
            rows = _fetch_klines(atlas, symbol, tf, 220)
            frames[tf] = analyze_price_action(rows, tf)
        except Exception as exc:
            frames[tf] = {'version': PRICE_ACTION_VERSION, 'timeframe': tf, 'ok': False, 'reason': 'FETCH_OR_ANALYSIS_ERROR'}
            errors[tf] = f'{type(exc).__name__}: {exc}'
    combined = combine_price_action({tf: {'price_action': frames[tf]} for tf in ('4h', '12h')})
    return {
        'version': VERSION,
        'analysis_version': PRICE_ACTION_VERSION,
        'frames': frames,
        'combined': combined,
        'fetch_errors': errors,
        'can_change_score': False,
        'can_change_threshold': False,
        'can_override_canonical_decision': False,
        'forward_evidence_required_before_promotion': True,
        'analysis_only': True,
        'live_execution': False,
    }


def install(atlas):
    if getattr(atlas, '_HTF_PRICE_ACTION_OVERLAY_INSTALLED', False):
        return getattr(atlas, 'HTF_PRICE_ACTION_OVERLAY_STATE', {'enabled': True, 'version': VERSION})
    original = atlas.production_decision

    def wrapped(symbol):
        row = original(symbol)
        if not isinstance(row, dict) or not row.get('ok'):
            return row
        sym = str(symbol or row.get('symbol') or '').upper().replace('BINANCE:', '')
        pa = build_live_price_action(atlas, sym)
        row['htf_price_action'] = pa
        row['htf_price_action_version'] = VERSION
        thesis = dict(row.get('htf_thesis') or {})
        thesis['price_action'] = pa
        row['htf_thesis'] = thesis
        matrix = dict(row.get('timeframe_matrix') or {})
        matrix['htf_price_action'] = pa
        row['timeframe_matrix'] = matrix
        plan = dict(row.get('trade_plan') or {})
        plan['htf_price_action_context'] = pa.get('combined')
        row['trade_plan'] = plan
        row['htf_price_action_score_preserved'] = True
        row['htf_price_action_threshold_preserved'] = True
        return row

    atlas.production_decision = wrapped
    atlas._HTF_PRICE_ACTION_OVERLAY_INSTALLED = True
    atlas.HTF_PRICE_ACTION_OVERLAY_STATE = {
        'enabled': True,
        'version': VERSION,
        'analysis_version': PRICE_ACTION_VERSION,
        'timeframes': ['4h', '12h'],
        'score_threshold_unchanged': True,
        'canonical_decision_override': False,
        'forward_evidence_required_before_promotion': True,
        'analysis_only': True,
        'live_execution': False,
    }
    return atlas.HTF_PRICE_ACTION_OVERLAY_STATE
