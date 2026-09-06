"""Freeze and settle ATLAS HTF scenario outcomes.

Research-only utility. A scenario is captured from the live decision payload and
later settled from CLOSED 4H candles. Trigger definition mirrors the scenario
engine: breakout/breakdown close plus retest confirmation. No Production state
is changed. Regression validation is enforced by Scenario Outcome Recorder CI.
"""
from __future__ import annotations

import datetime as dt

VERSION = 'SCENARIO_OUTCOME_RECORDER_V1'
HORIZONS = (4, 8, 12)


def _f(v, default=None):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def capture(decision, captured_at=None):
    scenario = (decision or {}).get('htf_scenario_engine') or {}
    selected = scenario.get('selected_case') or {}
    direction = str(selected.get('direction') or '').upper()
    if direction not in ('LONG', 'SHORT'):
        return None
    trigger = _f(selected.get('trigger_level'))
    invalidation = _f(selected.get('invalidation_level'))
    if trigger is None or invalidation is None:
        return None
    return {
        'recorder_version': VERSION,
        'scenario_version': scenario.get('version'),
        'symbol': (decision or {}).get('symbol'),
        'captured_at': captured_at or dt.datetime.now(dt.timezone.utc).isoformat(),
        'direction': direction,
        'trigger_type': selected.get('trigger_type'),
        'trigger_level': trigger,
        'invalidation_level': invalidation,
        'scenario_readiness': scenario.get('readiness'),
        'scenario_reason': scenario.get('reason'),
        'triggered': False,
        'triggered_at': None,
        'invalidated': False,
        'invalidated_at': None,
        'activation_price': None,
        # Raw market returns. Directional normalization belongs to calibration.
        'forward_return_pct': {},
        'research_only': True,
        'live_execution': False,
    }


def _ts(c):
    return c.get('close_time') or c.get('time') or c.get('timestamp')


def _closed(c):
    return c.get('closed', True) is True


def settle(record, candles4h):
    """Settle trigger/invalidation ordering from closed 4H candles.

    LONG trigger: a closed candle closes above trigger, followed by a later
    candle that trades back to/under trigger and still closes above it.
    SHORT is symmetric. Invalidation is a closed candle beyond the stored
    structural invalidation. Earliest completed event wins ordering.
    """
    out = dict(record or {})
    direction = str(out.get('direction') or '').upper()
    trigger = _f(out.get('trigger_level'))
    invalidation = _f(out.get('invalidation_level'))
    if direction not in ('LONG', 'SHORT') or trigger is None or invalidation is None:
        return out

    candles = [c for c in (candles4h or []) if _closed(c)]
    breakout_idx = None
    trigger_event = None
    invalidation_event = None

    for i, c in enumerate(candles):
        close = _f(c.get('close'))
        high = _f(c.get('high'))
        low = _f(c.get('low'))
        if close is None or high is None or low is None:
            continue

        if invalidation_event is None:
            if direction == 'LONG' and close < invalidation:
                invalidation_event = (_ts(c), close)
            elif direction == 'SHORT' and close > invalidation:
                invalidation_event = (_ts(c), close)

        if breakout_idx is None:
            if direction == 'LONG' and close > trigger:
                breakout_idx = i
            elif direction == 'SHORT' and close < trigger:
                breakout_idx = i
            continue

        if i <= breakout_idx:
            continue
        if trigger_event is None:
            if direction == 'LONG' and low <= trigger and close > trigger:
                trigger_event = (_ts(c), close)
            elif direction == 'SHORT' and high >= trigger and close < trigger:
                trigger_event = (_ts(c), close)

    if trigger_event is not None:
        out['triggered'] = True
        out['triggered_at'] = trigger_event[0]
        out['activation_price'] = trigger_event[1]
    if invalidation_event is not None:
        out['invalidated'] = True
        out['invalidated_at'] = invalidation_event[0]
    return out


def attach_forward_returns(record, hourly_candles):
    """Attach RAW market returns at 4/8/12H after activation.

    SHORT normalization is intentionally not performed here. The calibration
    engine normalizes raw market returns by direction exactly once.
    """
    out = dict(record or {})
    if not out.get('triggered') or not out.get('triggered_at'):
        return out
    entry = _f(out.get('activation_price'))
    if not entry:
        return out

    try:
        start = dt.datetime.fromisoformat(str(out['triggered_at']).replace('Z', '+00:00'))
    except Exception:
        return out

    returns = dict(out.get('forward_return_pct') or {})
    for h in HORIZONS:
        target = start + dt.timedelta(hours=h)
        candidates = []
        for c in hourly_candles or []:
            try:
                t = dt.datetime.fromisoformat(str(_ts(c)).replace('Z', '+00:00'))
            except Exception:
                continue
            if t >= target and _closed(c):
                close = _f(c.get('close'))
                if close is not None:
                    candidates.append((t, close))
        if not candidates:
            continue
        _, close = min(candidates, key=lambda x: x[0])
        raw = 100.0 * (close - entry) / entry
        returns[str(h)] = round(raw, 6)
    out['forward_return_pct'] = returns
    return out
