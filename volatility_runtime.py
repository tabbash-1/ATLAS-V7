"""ATLAS Volatility Forecast shadow runtime.

Installed as an additive overlay after Profit Engine and Microstructure runtime.
Historical price data is fetched only in a background refresh loop. Production
requests read a cached empirical forecast and attach descriptive geometry fits
for 1h/4h/12h; they never fetch candles, alter score/qualification/geometry, or
promote a trade.

For each newly stored explicit Production-qualified Forward row, the exact cached
forecast and geometry diagnostics available before the outcome are frozen to a
separate audit sidecar. Research rows and deduplicated Forward calls are excluded.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import volatility_forecast_engine

VERSION = 'VOLATILITY_RUNTIME_V1_OBSERVE_ONLY'
FORECAST_REFRESH_SECONDS = 300
HORIZONS_H = (1, 4, 12)


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


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


def _geometry_fits(forecast, direction, entry, stop_loss, target):
    return {
        str(h): volatility_forecast_engine.geometry_fit(
            forecast, direction, entry, stop_loss, target, horizon_h=h
        )
        for h in HORIZONS_H
    }


def install(collector):
    if getattr(collector, '_VOLATILITY_RUNTIME_INSTALLED', False):
        return getattr(collector, 'VOLATILITY_RUNTIME_STATE', {})

    original_decision = collector.production_decision
    original_forward_observe = getattr(collector, 'forward_observe', None)
    symbols = tuple(getattr(collector, 'ON_DEMAND_SYMBOLS', ()) or ())
    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    observation_file = data_dir / 'volatility_forecast_observations.jsonl'

    state = {
        'enabled': True,
        'version': VERSION,
        'shadow_only': True,
        'gate_mode': 'OBSERVE_ONLY',
        'gate_promoted': False,
        'can_override_production': False,
        'production_decision_mutation_allowed': False,
        'network_calls_in_decision_path': False,
        'observation_archive': str(observation_file),
        'forecast_by_symbol': {},
        'forecast_refreshes': 0,
        'frozen_signal_observations': 0,
        'research_observations_included': 0,
        'last_forecast_started_at': None,
        'last_forecast_finished_at': None,
        'last_forecast_errors': {},
        'last_error': None,
    }
    lock = threading.RLock()
    observation_lock = threading.RLock()

    # Count existing valid frozen rows without trusting malformed historical lines.
    if observation_file.exists():
        try:
            with observation_file.open(encoding='utf-8') as handle:
                state['frozen_signal_observations'] = sum(
                    1 for line in handle
                    if line.strip() and 'ATLAS_VOLATILITY_FORECAST_OBSERVATION_V1' in line
                )
        except Exception:
            pass

    def _now_iso():
        return collector.now_iso() if hasattr(collector, 'now_iso') else None

    def insufficient(normalized, reason='WAITING_FOR_BACKGROUND_VOLATILITY_REFRESH'):
        return {
            'version': volatility_forecast_engine.VERSION,
            'symbol': normalized,
            'status': 'INSUFFICIENT',
            'reason': reason,
            'horizons': {},
            'research_only': True,
            'shadow_only': True,
            'can_override_production': False,
            'probability_calibrated': False,
            'live_execution': False,
        }

    def refresh_forecasts():
        state['last_forecast_started_at'] = _now_iso()
        results = {}; errors = {}
        for symbol in symbols:
            normalized = str(symbol).upper().replace('BINANCE:', '')
            try:
                ks = collector._spot_klines(normalized)
                results[normalized] = volatility_forecast_engine.analyze(
                    normalized, ks, horizons_h=HORIZONS_H
                )
            except Exception as exc:
                errors[normalized] = f'{type(exc).__name__}: {exc}'
                results[normalized] = insufficient(normalized, 'VOLATILITY_FORECAST_REFRESH_FAILED')
                results[normalized]['error'] = errors[normalized]
        with lock:
            state['forecast_by_symbol'] = results
            state['forecast_refreshes'] += 1
            state['last_forecast_errors'] = errors
            state['last_error'] = (
                'volatility: ' + ' | '.join(f'{k}: {v}' for k, v in sorted(errors.items()))
                if errors else None
            )
        state['last_forecast_finished_at'] = _now_iso()
        return results

    def cached_forecast(normalized):
        with lock:
            cached = dict((state.get('forecast_by_symbol') or {}).get(normalized) or {})
        return cached if cached else insufficient(normalized)

    def production_decision_with_volatility_shadow(symbol):
        decision = original_decision(symbol)
        if not isinstance(decision, dict) or not decision.get('ok'):
            return decision
        normalized = str(decision.get('symbol') or symbol or '').upper().replace('BINANCE:', '')
        forecast = cached_forecast(normalized)
        fits = _geometry_fits(
            forecast,
            decision.get('candidate_direction'),
            decision.get('entry'),
            decision.get('stop_loss'),
            decision.get('take_profit'),
        )
        decision['volatility_shadow'] = {
            'version': VERSION,
            'forecast': forecast,
            'geometry_fit_by_horizon': fits,
            'evaluated_horizons_h': list(HORIZONS_H),
            'chosen_trade_horizon_assumed': False,
            'probability_calibrated': False,
            'gate_mode': 'OBSERVE_ONLY',
            'gate_promoted': False,
            'shadow_only': True,
            'can_override_production': False,
            'production_decision_unchanged': True,
            'production_actionable_decision': decision.get('actionable_decision'),
        }
        return decision

    def forward_observe_with_frozen_volatility(payload):
        qualified = bool(
            isinstance(payload, dict)
            and payload.get('production_signal_qualified') is True
        )
        frozen = None
        if qualified:
            normalized = str(payload.get('symbol') or '').upper().replace('BINANCE:', '')
            forecast = cached_forecast(normalized)
            stop = _derived_stop(payload)
            fits = _geometry_fits(
                forecast,
                payload.get('direction'),
                payload.get('entry'),
                stop,
                payload.get('structural_target'),
            )
            frozen = {
                'schema': 'ATLAS_VOLATILITY_FORECAST_OBSERVATION_V1',
                'captured_at': _now_iso(),
                'symbol': normalized,
                'direction': payload.get('direction'),
                'entry': _f(payload.get('entry')),
                'derived_stop_loss': stop,
                'structural_target': _f(payload.get('structural_target')),
                'gross_rr': _f(payload.get('rr_tp2')),
                'score': _f(payload.get('final_score')),
                'forecast': forecast,
                'geometry_fit_by_horizon': fits,
                'evaluated_horizons_h': list(HORIZONS_H),
                'chosen_trade_horizon_assumed': False,
                'production_signal_qualified': True,
                'research_sample': False,
                'research_samples_included': False,
                'outcome_known_at_capture': False,
                'probability_calibrated': False,
                'gate_mode': 'OBSERVE_ONLY',
                'gate_promoted': False,
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

    def forecast_loop():
        time.sleep(11)
        while True:
            refresh_forecasts()
            time.sleep(FORECAST_REFRESH_SECONDS)

    collector.production_decision = production_decision_with_volatility_shadow
    if callable(original_forward_observe):
        collector.forward_observe = forward_observe_with_frozen_volatility
    collector.VOLATILITY_RUNTIME_STATE = state
    collector.volatility_refresh_forecasts = refresh_forecasts
    collector._VOLATILITY_RUNTIME_INSTALLED = True
    threading.Thread(
        target=forecast_loop, daemon=True, name='atlas-volatility-forecast'
    ).start()
    return state
