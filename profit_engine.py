"""ATLAS Profit Decision Engine v3.

Conservative profit-readiness gate layered on top of Production scoring. It never
weakens or replaces Production qualification. Profit readiness requires an
independent asset regime aligned with the candidate, no strongly-opposed BTC
regime, valid geometry, calibrated TP/SL probability and a validated execution
cost model. Missing evidence fails closed to WAIT.
"""

VERSION = "ATLAS_PROFIT_ENGINE_V3_INDEPENDENT_REGIME"
MIN_NET_EV_R = 0.10
MIN_CALIBRATION_SAMPLES = 100

BULLISH_REGIMES = ('TREND_UP', 'BREAKOUT_UP', 'VOLATILITY_EXPANSION_UP')
BEARISH_REGIMES = ('TREND_DOWN', 'BREAKDOWN_DOWN', 'VOLATILITY_EXPANSION_DOWN')


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def regime_gate(row):
    row = row or {}
    direction = row.get('direction')
    regime = row.get('regime')
    btc_regime = row.get('btc_regime')
    asset_aligned = (
        direction == 'LONG' and regime in BULLISH_REGIMES
    ) or (
        direction == 'SHORT' and regime in BEARISH_REGIMES
    )
    btc_opposed = bool(
        (direction == 'LONG' and btc_regime in BEARISH_REGIMES) or
        (direction == 'SHORT' and btc_regime in BULLISH_REGIMES)
    )
    passed = bool(asset_aligned and not btc_opposed)
    if not asset_aligned:
        reason = 'ASSET_REGIME_NOT_ALIGNED'
    elif btc_opposed:
        reason = 'BTC_REGIME_OPPOSED'
    else:
        reason = 'REGIME_ALIGNED'
    return {
        'pass': passed,
        'asset_aligned': bool(asset_aligned),
        'btc_opposed': btc_opposed,
        'regime': regime,
        'btc_regime': btc_regime,
        'direction': direction,
        'reason': reason,
    }


def execution_cost_r(entry, stop, spread_bps=0.0, fee_bps=0.0, slippage_bps=0.0):
    entry = _f(entry); stop = _f(stop)
    if entry is None or stop is None or entry <= 0:
        return None
    risk_pct = abs(entry - stop) / entry
    if risk_pct <= 0:
        return None
    round_trip_pct = 2.0 * max(0.0, (_f(spread_bps, 0) + _f(fee_bps, 0) + _f(slippage_bps, 0))) / 10000.0
    return round_trip_pct / risk_pct


def expected_value_r(p_win, reward_r, loss_r=1.0, cost_r=0.0):
    p = _f(p_win); reward = _f(reward_r); loss = _f(loss_r, 1.0); cost = _f(cost_r, 0.0)
    if p is None or reward is None or not (0 <= p <= 1) or reward <= 0 or loss <= 0:
        return None
    return p * reward - (1.0 - p) * loss - max(0.0, cost)


def assess(row, *, stop_loss=None, calibration=None, execution=None):
    row = row or {}; calibration = calibration or {}; execution = execution or {}
    qualified = bool(row.get('production_signal_qualified'))
    regime = regime_gate(row)
    rr = _f(row.get('rr_tp2'))
    samples = int(calibration.get('samples') or 0)
    p_win = _f(calibration.get('p_win'))
    calibrated = bool(calibration.get('calibrated')) and samples >= MIN_CALIBRATION_SAMPLES and p_win is not None
    execution_validated = bool(execution.get('validated'))

    cost_r = None
    if execution_validated:
        cost_r = execution_cost_r(
            row.get('entry'), stop_loss,
            execution.get('spread_bps'), execution.get('fee_bps'), execution.get('slippage_bps'),
        )
    net_ev = expected_value_r(p_win, rr, cost_r=cost_r) if calibrated and execution_validated and cost_r is not None else None

    blockers = []
    if not qualified: blockers.append('NOT_PRODUCTION_QUALIFIED')
    if not regime['asset_aligned']: blockers.append('REGIME_NOT_ALIGNED')
    if regime['btc_opposed']: blockers.append('BTC_REGIME_OPPOSED')
    if rr is None or rr < 1.0: blockers.append('GEOMETRY_RR_BELOW_ONE')
    if not calibrated: blockers.append('CALIBRATION_WARMUP')
    if not execution_validated or cost_r is None: blockers.append('EXECUTION_COST_MODEL_UNAVAILABLE')
    if calibrated and execution_validated and net_ev is not None and net_ev < MIN_NET_EV_R:
        blockers.append('NET_EV_TOO_LOW')

    profit_ready = not blockers
    return {
        'version': VERSION,
        'profit_ready': profit_ready,
        'decision': row.get('direction') if profit_ready else 'WAIT',
        'blockers': blockers,
        'regime_gate': regime,
        'probability': {
            'calibrated': calibrated,
            'p_win': p_win,
            'samples': samples,
            'min_samples': MIN_CALIBRATION_SAMPLES,
            'basis': calibration.get('basis') or 'TP_SL_PATH_SETTLEMENT_REQUIRED',
        },
        'execution': {
            'validated': execution_validated,
            'spread_bps': _f(execution.get('spread_bps')),
            'fee_bps': _f(execution.get('fee_bps')),
            'slippage_bps': _f(execution.get('slippage_bps')),
            'basis': execution.get('basis') or 'REAL_EXECUTION_COST_MODEL_REQUIRED',
        },
        'execution_cost_r': round(cost_r, 6) if cost_r is not None else None,
        'gross_rr': rr,
        'net_expected_r': round(net_ev, 6) if net_ev is not None else None,
        'min_net_expected_r': MIN_NET_EV_R,
        'safety': 'FAIL_CLOSED_UNTIL_REGIME_CALIBRATION_AND_COSTS_VALIDATED',
    }
