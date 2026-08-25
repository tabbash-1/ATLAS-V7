"""Shadow runtime integration for ATLAS Profit Engine.

This layer never changes Production score qualification, thresholds, geometry or
live execution. It attaches a profit_engine_shadow payload to each decision.
Probability calibration is derived only from canonical Production-qualified
Frozen TP/SL path settlements (TP2 before SL vs SL before TP2), never from
research samples or directional 24h returns.

Calibration and execution-cost refreshes are background/cached so the decision
API never performs historical settlement or market-data I/O synchronously.
"""

from __future__ import annotations

import math
import threading
import time

import execution_cost_model
import execution_outcome_scope
import profit_engine
import trade_path_settlement

VERSION = 'PROFIT_ENGINE_RUNTIME_V2_PATH_CALIBRATION_LIVE_COSTS'
CALIBRATION_REFRESH_SECONDS = 900
COST_REFRESH_SECONDS = 120


def _wilson_interval(wins, total, z=1.96):
    if total <= 0:
        return None, None
    p = wins / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def build_path_calibration(collector):
    rows = collector.read_forward()
    geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
    execution_rows, rejected = execution_outcome_scope.filter_execution_rows(rows, geometry_map)
    items = trade_path_settlement.build_path_ledger(
        execution_rows, geometry_map, scope='all', limit=500
    )
    decisive = [x for x in items if x.get('path_outcome') in ('WIN_TP2', 'LOSS')]
    wins = sum(1 for x in decisive if x.get('path_outcome') == 'WIN_TP2')
    losses = sum(1 for x in decisive if x.get('path_outcome') == 'LOSS')
    samples = wins + losses
    p_win = (wins / samples) if samples else None
    low, high = _wilson_interval(wins, samples)
    calibrated = bool(samples >= profit_engine.MIN_CALIBRATION_SAMPLES and p_win is not None)
    return {
        'calibrated': calibrated,
        'samples': samples,
        'wins': wins,
        'losses': losses,
        'p_win': p_win,
        'p_win_ci95_low': low,
        'p_win_ci95_high': high,
        'basis': 'PRODUCTION_EXECUTION_SCOPE_TP2_BEFORE_SL_PATH_SETTLEMENT',
        'minimum_samples': profit_engine.MIN_CALIBRATION_SAMPLES,
        'execution_rows': len(execution_rows),
        'execution_rejected_rows': len(rejected),
        'research_samples_included': False,
        'directional_24h_returns_used': False,
    }


def install(collector):
    if getattr(collector, '_PROFIT_ENGINE_RUNTIME_INSTALLED', False):
        return getattr(collector, 'PROFIT_ENGINE_RUNTIME_STATE', {})

    original_decision = collector.production_decision
    symbols = tuple(getattr(collector, 'ON_DEMAND_SYMBOLS', ()) or ())
    state = {
        'enabled': True,
        'version': VERSION,
        'shadow_only': True,
        'can_override_production': False,
        'calibration': {
            'calibrated': False,
            'samples': 0,
            'p_win': None,
            'basis': 'PRODUCTION_EXECUTION_SCOPE_TP2_BEFORE_SL_PATH_SETTLEMENT',
            'minimum_samples': profit_engine.MIN_CALIBRATION_SAMPLES,
        },
        'execution_cost_by_symbol': {},
        'calibration_refreshes': 0,
        'cost_refreshes': 0,
        'last_calibration_started_at': None,
        'last_calibration_finished_at': None,
        'last_cost_started_at': None,
        'last_cost_finished_at': None,
        'last_error': None,
        'last_cost_errors': {},
    }
    lock = threading.RLock()

    def refresh_calibration():
        state['last_calibration_started_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        try:
            result = build_path_calibration(collector)
            with lock:
                state['calibration'] = result
                state['calibration_refreshes'] += 1
                state['last_error'] = None
            return result
        except Exception as exc:
            with lock:
                state['last_error'] = f'calibration: {type(exc).__name__}: {exc}'
            return None
        finally:
            state['last_calibration_finished_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None

    def refresh_execution_costs():
        state['last_cost_started_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        results = {}
        errors = {}
        ua = getattr(collector, 'UA', 'ATLAS-Research/1.0')
        for symbol in symbols:
            normalized = str(symbol).upper().replace('BINANCE:', '')
            try:
                results[normalized] = execution_cost_model.estimate(normalized, ua=ua)
            except Exception as exc:
                errors[normalized] = f'{type(exc).__name__}: {exc}'
                results[normalized] = {
                    'version': execution_cost_model.VERSION,
                    'symbol': normalized,
                    'validated': False,
                    'blockers': ['EXECUTION_COST_FETCH_FAILED'],
                    'basis': 'LIVE_OKX_SWAP_L2_PLUS_CONFIGURED_TAKER_FEE',
                    'error': errors[normalized],
                    'research_only': True,
                    'live_execution': False,
                }
        with lock:
            state['execution_cost_by_symbol'] = results
            state['last_cost_errors'] = errors
            state['cost_refreshes'] += 1
            if errors:
                state['last_error'] = 'execution_cost: ' + ' | '.join(f'{k}: {v}' for k, v in sorted(errors.items()))
            elif str(state.get('last_error') or '').startswith('execution_cost:'):
                state['last_error'] = None
        state['last_cost_finished_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        return results

    def calibration_loop():
        time.sleep(20)
        while True:
            refresh_calibration()
            time.sleep(CALIBRATION_REFRESH_SECONDS)

    def cost_loop():
        time.sleep(5)
        while True:
            refresh_execution_costs()
            time.sleep(COST_REFRESH_SECONDS)

    def production_decision_with_profit_shadow(symbol):
        decision = original_decision(symbol)
        if not isinstance(decision, dict) or not decision.get('ok'):
            return decision
        normalized = str(decision.get('symbol') or symbol or '').upper().replace('BINANCE:', '')
        with lock:
            calibration = dict(state.get('calibration') or {})
            execution = dict((state.get('execution_cost_by_symbol') or {}).get(normalized) or {
                'validated': False,
                'basis': 'WAITING_FOR_BACKGROUND_EXECUTION_COST_REFRESH',
            })
        row = {
            'production_signal_qualified': bool(decision.get('production_signal_qualified')),
            'direction': decision.get('candidate_direction'),
            'regime': decision.get('regime'),
            'entry': decision.get('entry'),
            'rr_tp2': decision.get('risk_reward'),
        }
        shadow = profit_engine.assess(
            row,
            stop_loss=decision.get('stop_loss'),
            calibration=calibration,
            execution=execution,
        )
        shadow.update({
            'shadow_only': True,
            'can_override_production': False,
            'production_decision_unchanged': True,
            'production_actionable_decision': decision.get('actionable_decision'),
            'execution_cost_source_version': execution.get('version'),
            'execution_cost_blockers': execution.get('blockers') or [],
        })
        decision['profit_engine_shadow'] = shadow
        decision['profit_engine_version'] = profit_engine.VERSION
        return decision

    collector.production_decision = production_decision_with_profit_shadow
    collector.PROFIT_ENGINE_RUNTIME_STATE = state
    collector.profit_engine_refresh_calibration = refresh_calibration
    collector.profit_engine_refresh_execution_costs = refresh_execution_costs
    collector._PROFIT_ENGINE_RUNTIME_INSTALLED = True
    threading.Thread(target=calibration_loop, daemon=True, name='atlas-profit-calibration').start()
    threading.Thread(target=cost_loop, daemon=True, name='atlas-profit-costs').start()
    return state
