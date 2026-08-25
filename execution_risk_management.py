"""ATLAS execution risk-management overlay.

Additive safety layer: score/direction logic remains untouched. New observations
freeze structural geometry, outcome reports preserve an unmanaged baseline, and
management plans are exposed only when their level order and actual R:R are valid.
"""

MIN_EXECUTION_RR = 1.0
TP1_REALIZE_FRACTION = 0.50
REMAINDER_FRACTION = 1.0 - TP1_REALIZE_FRACTION
POLICY_VERSION = 'ATLAS_EXECUTION_RISK_V1_STRUCTURAL_TP1_PROTECT'


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _valid_level_order(direction, entry, stop, tp1, tp2):
    if any(v is None or v <= 0 for v in (entry, stop, tp1, tp2)):
        return False
    if direction == 'LONG':
        return stop < entry < tp1 <= tp2
    if direction == 'SHORT':
        return tp2 <= tp1 < entry < stop
    return False


def _actual_rr(entry, stop, tp2):
    risk = abs(entry - stop) if entry is not None and stop is not None else 0.0
    reward = abs(tp2 - entry) if entry is not None and tp2 is not None else 0.0
    return reward / risk if risk > 0 else None


def derive_structural_geometry(payload):
    """Freeze actual support/resistance geometry instead of back-solving SL from RR."""
    x = dict(payload or {})
    entry = _fnum(x.get('entry'))
    direction = str(x.get('direction') or '').upper()
    support_distance = _fnum(x.get('support_distance_pct'))
    resistance_distance = _fnum(x.get('resistance_distance_pct'))
    if not entry or entry <= 0 or direction not in ('LONG', 'SHORT'):
        return None
    if support_distance is None or resistance_distance is None:
        return None
    if support_distance <= 0 or resistance_distance <= 0:
        return None

    if direction == 'LONG':
        risk = entry * support_distance / 100.0
        reward = entry * resistance_distance / 100.0
        stop, tp1, tp2 = entry - risk, entry + risk, entry + reward
    else:
        risk = entry * resistance_distance / 100.0
        reward = entry * support_distance / 100.0
        stop, tp1, tp2 = entry + risk, entry - risk, entry - reward

    rr2 = reward / risk if risk > 0 else None
    if rr2 is None or rr2 < MIN_EXECUTION_RR:
        return None
    if not _valid_level_order(direction, entry, stop, tp1, tp2):
        return None

    return {
        'entry': round(entry, 12),
        'stop_loss': round(stop, 12),
        'tp1': round(tp1, 12),
        'tp2': round(tp2, 12),
        'risk_abs': round(risk, 12),
        'rr_tp1': 1.0,
        'rr_tp2': round(rr2, 6),
        'direction': direction,
        'method': 'STRUCTURAL_SUPPORT_RESISTANCE_ACTUAL_RR',
        'tp1_method': 'ONE_R_CHECKPOINT',
        'tp1_is_terminal_exit': False,
        'management_policy': POLICY_VERSION,
        'tp1_realize_fraction': TP1_REALIZE_FRACTION,
        'remainder_stop_after_tp1': 'BREAKEVEN_ENTRY',
        'frozen_at_observation': True,
        'legacy_rr_input': _fnum(x.get('rr_tp2')),
    }


def manage_settlement_result(raw):
    """Counterfactual managed result: 50% at TP1, remainder protected at entry."""
    out = dict(raw or {})
    raw_outcome = out.get('path_outcome')
    raw_r = out.get('r_multiple')
    out['raw_unmanaged_path_outcome'] = raw_outcome
    out['raw_unmanaged_r_multiple'] = raw_r
    out['management_policy'] = POLICY_VERSION
    out['tp1_realize_fraction'] = TP1_REALIZE_FRACTION

    if raw_outcome == 'LOSS' and out.get('tp1_reached'):
        out['path_outcome'] = 'WIN_TP1_PROTECTED'
        out['path_event'] = 'TP1_THEN_BREAKEVEN'
        out['r_multiple'] = round(TP1_REALIZE_FRACTION, 6)
        out['terminal'] = True
        out['management_exit'] = 'REMAINDER_STOPPED_AT_BREAKEVEN_AFTER_TP1'
    elif raw_outcome == 'WIN_TP2' and raw_r is not None:
        out['r_multiple'] = round(TP1_REALIZE_FRACTION + REMAINDER_FRACTION * float(raw_r), 6)
        out['management_exit'] = 'HALF_AT_TP1_REMAINDER_AT_TP2'
    elif raw_outcome == 'EXPIRED_AFTER_TP1':
        out['path_outcome'] = 'WIN_TP1_PROTECTED_EXPIRED'
        out['r_multiple'] = round(TP1_REALIZE_FRACTION, 6)
        out['terminal'] = True
        out['management_exit'] = 'HALF_AT_TP1_REMAINDER_PROTECTED_TO_HORIZON'
    elif raw_outcome == 'OPEN_AFTER_TP1':
        out['realized_r_multiple'] = round(TP1_REALIZE_FRACTION, 6)
        out['protected_stop'] = out.get('entry')
        out['management_exit'] = 'HALF_REALIZED_REMAINDER_PROTECTED_AT_BREAKEVEN'
    return out


def summarize_managed_path(items, baseline_summary=None):
    items = list(items or [])
    terminal = [x for x in items if x.get('terminal')]
    economic = [(x, _fnum(x.get('r_multiple'))) for x in terminal]
    wins = [x for x, r in economic if r is not None and r > 0]
    losses = [x for x, r in economic if r is not None and r < 0]
    flat = [x for x, r in economic if r == 0]
    rs = [r for _, r in economic if r is not None]
    positive = sum(r for r in rs if r > 0)
    negative = abs(sum(r for r in rs if r < 0))
    result = dict(baseline_summary or {})
    result.update({
        'terminal': len(terminal),
        'open': len(items) - len(terminal),
        'wins': len(wins),
        'losses': len(losses),
        'flat': len(flat),
        'win_rate_pct': round(100.0 * len(wins) / (len(wins) + len(losses)), 2) if wins or losses else None,
        'net_r': round(sum(rs), 4) if rs else None,
        'average_r': round(sum(rs) / len(rs), 4) if rs else None,
        'profit_factor_r': round(positive / negative, 4) if negative > 0 else ('INF' if positive > 0 else None),
        'protected_tp1_exits': sum(1 for x in items if x.get('path_outcome') in ('WIN_TP1_PROTECTED', 'WIN_TP1_PROTECTED_EXPIRED')),
        'management_policy': POLICY_VERSION,
    })
    return result


def _execution_geometry_from_live(atlas, symbol, decision):
    entry = _fnum((decision or {}).get('entry'))
    direction = str((decision or {}).get('candidate_direction') or '').upper()
    atr = _fnum(((decision or {}).get('indicators') or {}).get('atr14'))
    if not entry or entry <= 0 or direction not in ('LONG', 'SHORT') or not atr or atr <= 0:
        return None
    try:
        ks = atlas._spot_klines(symbol)
        support, resistance, _, _ = atlas._cloud_sr(ks)
        support, resistance = _fnum(support), _fnum(resistance)
    except Exception:
        return None

    if direction == 'LONG':
        target = resistance if resistance is not None and resistance > entry else None
        atr_stop = entry - 1.2 * atr
        structural_stop = support if support is not None and support < entry else None
        stops = [x for x in (atr_stop, structural_stop) if x is not None and 0 < x < entry]
        stop = min(stops) if stops else None
    else:
        target = support if support is not None and support < entry else None
        atr_stop = entry + 1.2 * atr
        structural_stop = resistance if resistance is not None and resistance > entry else None
        stops = [x for x in (atr_stop, structural_stop) if x is not None and x > entry]
        stop = max(stops) if stops else None

    if stop is None or target is None:
        return None
    risk = abs(entry - stop)
    rr = _actual_rr(entry, stop, target)
    if rr is None:
        return None
    tp1 = entry + risk if direction == 'LONG' else entry - risk
    valid = _valid_level_order(direction, entry, stop, tp1, target) and rr >= MIN_EXECUTION_RR
    return {
        'entry': entry, 'stop_loss': stop, 'tp1': tp1, 'tp2': target,
        'risk_reward': rr, 'valid': bool(valid), 'direction': direction,
        'support': support, 'resistance': resistance,
    }


def _management_plan(direction, entry, stop, tp1, tp2, source, status=None):
    direction = str(direction or '').upper()
    entry, stop, tp1, tp2 = map(_fnum, (entry, stop, tp1, tp2))
    rr = _actual_rr(entry, stop, tp2)
    if not _valid_level_order(direction, entry, stop, tp1, tp2):
        return None
    if rr is None or rr < MIN_EXECUTION_RR:
        return None
    return {
        'policy': POLICY_VERSION,
        'source': source,
        'status': status or 'READY',
        'direction': direction,
        'entry': round(entry, 10),
        'initial_stop_loss': round(stop, 10),
        'tp1': round(tp1, 10),
        'tp1_close_fraction': TP1_REALIZE_FRACTION,
        'after_tp1_stop': round(entry, 10),
        'tp2': round(tp2, 10),
        'rr_tp2_actual': round(rr, 6),
        'remainder_fraction': REMAINDER_FRACTION,
    }


def _managed_plan_from_trade_plan(plan):
    if not isinstance(plan, dict):
        return None
    status = str(plan.get('status') or '').upper()
    return _management_plan(
        plan.get('direction'), plan.get('entry'), plan.get('stop_loss'),
        plan.get('tp1'), plan.get('tp2'), 'TRADE_PLAN',
        'CONDITIONAL_ARMED' if status == 'CONDITIONAL' else 'READY',
    )


def install(atlas):
    """Install additive live-decision and outcome-settlement corrections."""
    import trade_path_settlement as tps

    if getattr(atlas, '_EXECUTION_RISK_MANAGEMENT_INSTALLED', False):
        return getattr(atlas, 'EXECUTION_RISK_MANAGEMENT_STATE', {})

    tps.derive_geometry = derive_structural_geometry
    original_settle = tps.settle_row
    original_summary = tps.summarize_path

    def managed_settle(*args, **kwargs):
        return manage_settlement_result(original_settle(*args, **kwargs))

    def managed_summary(items):
        items = list(items or [])
        raw_items = []
        for item in items:
            raw = dict(item)
            if 'raw_unmanaged_path_outcome' in item:
                raw['path_outcome'] = item.get('raw_unmanaged_path_outcome')
                raw['r_multiple'] = item.get('raw_unmanaged_r_multiple')
            raw_items.append(raw)
        baseline = original_summary(raw_items)
        managed = summarize_managed_path(items, baseline_summary=baseline)
        managed['unmanaged_baseline'] = {
            'wins': baseline.get('wins'), 'losses': baseline.get('losses'),
            'win_rate_pct': baseline.get('win_rate_pct'), 'net_r': baseline.get('net_r'),
            'average_r': baseline.get('average_r'), 'profit_factor_r': baseline.get('profit_factor_r'),
        }
        return managed

    tps.settle_row = managed_settle
    tps.summarize_path = managed_summary

    original_decision = getattr(atlas, 'production_decision', None)
    if callable(original_decision):
        def production_decision_with_risk(symbol):
            result = original_decision(symbol)
            if not isinstance(result, dict) or not result.get('ok'):
                return result

            result['execution_policy_version'] = POLICY_VERSION

            # Final decision-engine trade plans take precedence. Conditional
            # entries must be managed from their own entry/SL/TP geometry, not
            # from the current spot price.
            final_plan = _managed_plan_from_trade_plan(result.get('trade_plan'))
            if final_plan is not None:
                result['management_plan'] = final_plan
                result['management_plan_status'] = final_plan['status']
                return result

            geometry = _execution_geometry_from_live(
                atlas, str(symbol or '').upper().replace('BINANCE:', ''), result
            )
            qualified = bool(result.get('production_signal_qualified'))

            if geometry is None:
                result['management_plan'] = None
                result['management_plan_status'] = 'BLOCKED_GEOMETRY_UNAVAILABLE'
                result['execution_ready'] = False
                result['actionable_decision'] = 'WAIT'
                result['actionable_reason'] = 'STRUCTURAL_GEOMETRY_UNAVAILABLE'
                result['geometry_gate'] = {
                    'status': 'BLOCK', 'qualified': False,
                    'reason': 'STRUCTURAL_GEOMETRY_UNAVAILABLE',
                    'min_risk_reward': MIN_EXECUTION_RR,
                }
                return result

            rr = geometry['risk_reward']
            result['stop_loss'] = round(geometry['stop_loss'], 10)
            result['take_profit'] = round(geometry['tp2'], 10)
            result['risk_reward'] = round(rr, 6)
            ready = bool(qualified and geometry['valid'])
            result['execution_ready'] = ready
            result['actionable_decision'] = result.get('candidate_direction') if ready else 'WAIT'
            result['actionable_reason'] = 'EXECUTION_READY_STRUCTURAL' if ready else 'STRUCTURAL_RR_BELOW_ONE_TO_ONE'
            result['geometry_gate'] = {
                'status': 'PASS' if geometry['valid'] else 'BLOCK',
                'qualified': geometry['valid'],
                'reason': 'STRUCTURE_PLUS_ATR_FLOOR_ACTUAL_RR' if geometry['valid'] else 'STRUCTURAL_RR_BELOW_ONE_TO_ONE',
                'min_risk_reward': MIN_EXECUTION_RR,
                'risk_reward': round(rr, 6),
                'stop_method': 'FARTHER_OF_STRUCTURE_OR_1_2_ATR',
                'target_method': 'NEXT_STRUCTURAL_SUPPORT_RESISTANCE',
            }

            if ready:
                result['trade_plan_status'] = 'EXECUTION_READY_STRUCTURAL_MANAGED'
                result['management_plan'] = _management_plan(
                    geometry['direction'], geometry['entry'], geometry['stop_loss'],
                    geometry['tp1'], geometry['tp2'], 'LIVE_STRUCTURAL_GEOMETRY', 'READY'
                )
                result['management_plan_status'] = 'READY'
            else:
                result['management_plan'] = None
                result['management_plan_status'] = 'BLOCKED_INVALID_GEOMETRY'
            return result

        atlas.production_decision = production_decision_with_risk

    state = {
        'enabled': True,
        'policy': POLICY_VERSION,
        'min_execution_rr': MIN_EXECUTION_RR,
        'tp1_realize_fraction': TP1_REALIZE_FRACTION,
        'remainder_stop_after_tp1': 'BREAKEVEN_ENTRY',
        'new_geometry_method': 'STRUCTURAL_SUPPORT_RESISTANCE_ACTUAL_RR',
        'management_plan_requires_valid_geometry': True,
        'conditional_plan_source': 'TRADE_PLAN',
        'historical_geometry_rewritten': False,
    }
    atlas.EXECUTION_RISK_MANAGEMENT_STATE = state
    atlas._EXECUTION_RISK_MANAGEMENT_INSTALLED = True
    return state
