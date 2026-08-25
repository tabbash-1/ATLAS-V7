"""Shadow runtime integration for ATLAS Profit Engine.

This layer never changes Production score qualification, thresholds, geometry or
live execution. It attaches a profit_engine_shadow payload to each decision.
Probability calibration comes only from canonical Production-qualified Frozen
TP/SL path settlements. Execution costs come from a cached live L2 model. Market
regime is classified independently from signal direction and cached in the
background.

For every newly stored Production-qualified Forward row, the exact Profit Engine
evidence available at observation time is frozen into a separate sidecar audit
archive. Research rows are never written to this archive. This prevents hindsight
bias when the Profit Engine is evaluated later.

A background prequential walk-forward report later joins those frozen-at-signal
observations to canonical TP/SL settlements. Historical regime/cost/probability
inputs are never recomputed with future information.
"""

from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path

import execution_cost_model
import execution_outcome_scope
import market_regime_engine
import profit_engine
import profit_engine_walkforward
import trade_path_settlement

VERSION = 'PROFIT_ENGINE_RUNTIME_V5_BACKGROUND_WALKFORWARD'
CALIBRATION_REFRESH_SECONDS = 900
COST_REFRESH_SECONDS = 120
REGIME_REFRESH_SECONDS = 300
WALKFORWARD_REFRESH_SECONDS = 900


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _wilson_interval(wins, total, z=1.96):
    if total <= 0:
        return None, None
    p = wins / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def _derived_stop(payload):
    entry = _f((payload or {}).get('entry'))
    target = _f((payload or {}).get('structural_target'))
    rr = _f((payload or {}).get('rr_tp2'))
    direction = str((payload or {}).get('direction') or '').upper()
    if entry is None or target is None or rr is None or rr <= 0 or direction not in ('LONG', 'SHORT'):
        return None
    reward = (target - entry) if direction == 'LONG' else (entry - target)
    if reward <= 0:
        return None
    risk = reward / rr
    return entry - risk if direction == 'LONG' else entry + risk


def _execution_settlements(collector):
    """Canonical Production execution scope only; Research rows are rejected."""
    rows = collector.read_forward()
    geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
    execution_rows, rejected = execution_outcome_scope.filter_execution_rows(rows, geometry_map)
    items = trade_path_settlement.build_path_ledger(execution_rows, geometry_map, scope='all', limit=500)
    return items, execution_rows, rejected


def build_path_calibration(collector):
    items, execution_rows, rejected = _execution_settlements(collector)
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


def build_walkforward_report(collector, observation_file):
    """Evaluate only evidence frozen before outcomes were known."""
    observations = profit_engine_walkforward.read_observations(observation_file)
    settlements, execution_rows, rejected = _execution_settlements(collector)
    report = profit_engine_walkforward.report(observations, settlements)
    report['canonical_execution_rows'] = len(execution_rows)
    report['canonical_execution_rejected_rows'] = len(rejected)
    report['observation_archive'] = str(observation_file)
    report['runtime_version'] = VERSION
    return report


def install(collector):
    if getattr(collector, '_PROFIT_ENGINE_RUNTIME_INSTALLED', False):
        return getattr(collector, 'PROFIT_ENGINE_RUNTIME_STATE', {})

    original_decision = collector.production_decision
    original_forward_observe = getattr(collector, 'forward_observe', None)
    symbols = tuple(getattr(collector, 'ON_DEMAND_SYMBOLS', ()) or ())
    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    observation_file = data_dir / 'profit_engine_observations.jsonl'
    existing_frozen = len(profit_engine_walkforward.read_observations(observation_file))
    state = {
        'enabled': True,
        'version': VERSION,
        'shadow_only': True,
        'can_override_production': False,
        'observation_archive': str(observation_file),
        'frozen_signal_observations': existing_frozen,
        'research_observations_included': 0,
        'calibration': {
            'calibrated': False,
            'samples': 0,
            'p_win': None,
            'basis': 'PRODUCTION_EXECUTION_SCOPE_TP2_BEFORE_SL_PATH_SETTLEMENT',
            'minimum_samples': profit_engine.MIN_CALIBRATION_SAMPLES,
        },
        'execution_cost_by_symbol': {},
        'market_regime_by_symbol': {},
        'walk_forward_report': {
            'version': profit_engine_walkforward.VERSION,
            'status': 'COLLECTING',
            'improves_production_expectancy': False,
            'blockers': ['WAITING_FOR_BACKGROUND_WALK_FORWARD_REFRESH'],
            'frozen_observations': existing_frozen,
            'research_samples_included': False,
            'shadow_only': True,
            'can_override_production': False,
        },
        'calibration_refreshes': 0,
        'cost_refreshes': 0,
        'regime_refreshes': 0,
        'walkforward_refreshes': 0,
        'last_calibration_started_at': None,
        'last_calibration_finished_at': None,
        'last_cost_started_at': None,
        'last_cost_finished_at': None,
        'last_regime_started_at': None,
        'last_regime_finished_at': None,
        'last_walkforward_started_at': None,
        'last_walkforward_finished_at': None,
        'last_error': None,
        'last_cost_errors': {},
        'last_regime_errors': {},
        'last_walkforward_error': None,
    }
    lock = threading.RLock()
    observation_lock = threading.RLock()

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
        results = {}; errors = {}
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

    def refresh_market_regimes():
        state['last_regime_started_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        results = {}; errors = {}
        try:
            btc_ks = collector._spot_klines('BTCUSDT')
        except Exception as exc:
            btc_ks = []
            errors['BTCUSDT'] = f'{type(exc).__name__}: {exc}'
        for symbol in symbols:
            normalized = str(symbol).upper().replace('BINANCE:', '')
            try:
                asset_ks = btc_ks if normalized == 'BTCUSDT' else collector._spot_klines(normalized)
                results[normalized] = market_regime_engine.analyze(normalized, asset_ks, btc_ks)
            except Exception as exc:
                errors[normalized] = f'{type(exc).__name__}: {exc}'
                results[normalized] = {
                    'symbol': normalized,
                    'asset_regime': 'UNKNOWN',
                    'btc_regime': 'UNKNOWN',
                    'version': market_regime_engine.VERSION,
                    'error': errors[normalized],
                    'shadow_only': True,
                    'can_override_production': False,
                }
        with lock:
            state['market_regime_by_symbol'] = results
            state['last_regime_errors'] = errors
            state['regime_refreshes'] += 1
            if errors:
                state['last_error'] = 'regime: ' + ' | '.join(f'{k}: {v}' for k, v in sorted(errors.items()))
            elif str(state.get('last_error') or '').startswith('regime:'):
                state['last_error'] = None
        state['last_regime_finished_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        return results

    def refresh_walkforward():
        state['last_walkforward_started_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        try:
            result = build_walkforward_report(collector, observation_file)
            with lock:
                state['walk_forward_report'] = result
                state['walkforward_refreshes'] += 1
                state['last_walkforward_error'] = None
            return result
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            with lock:
                state['last_walkforward_error'] = error
                state['walk_forward_report'] = {
                    'version': profit_engine_walkforward.VERSION,
                    'status': 'UNAVAILABLE',
                    'improves_production_expectancy': False,
                    'blockers': ['WALK_FORWARD_REFRESH_ERROR'],
                    'error': error,
                    'research_samples_included': False,
                    'shadow_only': True,
                    'can_override_production': False,
                }
            return None
        finally:
            state['last_walkforward_finished_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None

    def cached_evidence(normalized):
        with lock:
            calibration = dict(state.get('calibration') or {})
            execution = dict((state.get('execution_cost_by_symbol') or {}).get(normalized) or {
                'validated': False,
                'basis': 'WAITING_FOR_BACKGROUND_EXECUTION_COST_REFRESH',
            })
            regime_context = dict((state.get('market_regime_by_symbol') or {}).get(normalized) or {
                'asset_regime': 'UNKNOWN',
                'btc_regime': 'UNKNOWN',
                'version': market_regime_engine.VERSION,
                'shadow_only': True,
            })
        return calibration, execution, regime_context

    def assess_payload(payload, normalized, stop_loss=None):
        calibration, execution, regime_context = cached_evidence(normalized)
        row = {
            'production_signal_qualified': bool((payload or {}).get('production_signal_qualified')),
            'direction': (payload or {}).get('direction'),
            'regime': regime_context.get('asset_regime') or 'UNKNOWN',
            'btc_regime': regime_context.get('btc_regime') or 'UNKNOWN',
            'entry': (payload or {}).get('entry'),
            'rr_tp2': (payload or {}).get('rr_tp2'),
        }
        shadow = profit_engine.assess(row, stop_loss=stop_loss, calibration=calibration, execution=execution)
        return shadow, calibration, execution, regime_context

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

    def regime_loop():
        time.sleep(7)
        while True:
            refresh_market_regimes()
            time.sleep(REGIME_REFRESH_SECONDS)

    def walkforward_loop():
        # Run after calibration and market-data warmup so path settlement can use
        # normal caches/circuit breakers rather than competing with boot traffic.
        time.sleep(35)
        while True:
            refresh_walkforward()
            time.sleep(WALKFORWARD_REFRESH_SECONDS)

    def production_decision_with_profit_shadow(symbol):
        decision = original_decision(symbol)
        if not isinstance(decision, dict) or not decision.get('ok'):
            return decision
        normalized = str(decision.get('symbol') or symbol or '').upper().replace('BINANCE:', '')
        payload = {
            'production_signal_qualified': bool(decision.get('production_signal_qualified')),
            'direction': decision.get('candidate_direction'),
            'entry': decision.get('entry'),
            'rr_tp2': decision.get('risk_reward'),
        }
        shadow, _calibration, execution, regime_context = assess_payload(payload, normalized, decision.get('stop_loss'))
        shadow.update({
            'shadow_only': True,
            'can_override_production': False,
            'production_decision_unchanged': True,
            'production_actionable_decision': decision.get('actionable_decision'),
            'execution_cost_source_version': execution.get('version'),
            'execution_cost_blockers': execution.get('blockers') or [],
            'market_regime': regime_context,
            'production_legacy_regime': decision.get('regime'),
        })
        decision['profit_engine_shadow'] = shadow
        decision['profit_engine_version'] = profit_engine.VERSION
        return decision

    def forward_observe_with_frozen_profit_evidence(payload):
        # Strictly require the explicit Production qualification flag. Never infer
        # qualification from a research score or champion flag.
        qualified = bool(isinstance(payload, dict) and payload.get('production_signal_qualified') is True)
        frozen = None
        if qualified:
            normalized = str(payload.get('symbol') or '').upper().replace('BINANCE:', '')
            stop = _derived_stop(payload)
            shadow, calibration, execution, regime_context = assess_payload(payload, normalized, stop)
            frozen = {
                'schema': 'ATLAS_PROFIT_ENGINE_OBSERVATION_V1',
                'captured_at': collector.now_iso() if hasattr(collector, 'now_iso') else None,
                'symbol': normalized,
                'direction': payload.get('direction'),
                'entry': _f(payload.get('entry')),
                'score': _f(payload.get('final_score')),
                'signal_threshold': _f(payload.get('signal_threshold'), _f(getattr(collector, 'CLOUD_FORWARD_MIN_SCORE', None))),
                'derived_stop_loss': stop,
                'structural_target': _f(payload.get('structural_target')),
                'gross_rr': _f(payload.get('rr_tp2')),
                'profit_engine': shadow,
                'market_regime': regime_context,
                'execution_cost': execution,
                'calibration': calibration,
                'production_signal_qualified': True,
                'research_sample': False,
                'research_samples_included': False,
                'outcome_known_at_capture': False,
                'shadow_only': True,
                'can_override_production': False,
                'runtime_version': VERSION,
            }
        result = original_forward_observe(payload)
        if frozen is not None and isinstance(result, dict) and result.get('id'):
            frozen['forward_id'] = result.get('id')
            frozen['forward_captured_at_ms'] = result.get('captured_at_ms')
            with observation_lock:
                observation_file.parent.mkdir(parents=True, exist_ok=True)
                with observation_file.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(frozen, separators=(',', ':')) + '\n')
            with lock:
                state['frozen_signal_observations'] += 1
        return result

    collector.production_decision = production_decision_with_profit_shadow
    if callable(original_forward_observe):
        collector.forward_observe = forward_observe_with_frozen_profit_evidence
    collector.PROFIT_ENGINE_RUNTIME_STATE = state
    collector.profit_engine_refresh_calibration = refresh_calibration
    collector.profit_engine_refresh_execution_costs = refresh_execution_costs
    collector.profit_engine_refresh_market_regimes = refresh_market_regimes
    collector.profit_engine_refresh_walkforward = refresh_walkforward
    collector._PROFIT_ENGINE_RUNTIME_INSTALLED = True
    threading.Thread(target=calibration_loop, daemon=True, name='atlas-profit-calibration').start()
    threading.Thread(target=cost_loop, daemon=True, name='atlas-profit-costs').start()
    threading.Thread(target=regime_loop, daemon=True, name='atlas-market-regime').start()
    threading.Thread(target=walkforward_loop, daemon=True, name='atlas-profit-walkforward').start()
    return state
