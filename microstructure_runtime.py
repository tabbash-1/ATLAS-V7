"""ATLAS Microstructure shadow runtime.

This overlay is deliberately installed after Profit Engine runtime so wrappers
chain without modifying Production qualification, score, geometry or execution.
It keeps a cached rolling Futures microstructure context, attaches it to decisions
for observability, freezes that exact context only when a new explicit
Production-qualified Forward row is stored, and later evaluates the frozen
context against canonical TP/SL settlements.

No network or archive scan is performed in the Production decision request path.
Microstructure is OBSERVE_ONLY until forward evidence independently supports a
future gate and that gate is separately promoted.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import execution_outcome_scope
import microstructure_memory
import microstructure_walkforward
import trade_path_settlement

VERSION = 'MICROSTRUCTURE_RUNTIME_V1_OBSERVE_ONLY'
MEMORY_REFRESH_SECONDS = 300
WALKFORWARD_REFRESH_SECONDS = 900


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _execution_settlements(collector):
    rows = collector.read_forward()
    geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
    execution_rows, rejected = execution_outcome_scope.filter_execution_rows(rows, geometry_map)
    settlements = trade_path_settlement.build_path_ledger(
        execution_rows, geometry_map, scope='all', limit=500
    )
    return settlements, execution_rows, rejected


def build_walkforward_report(collector, observation_file):
    observations = microstructure_walkforward.read_observations(observation_file)
    settlements, execution_rows, rejected = _execution_settlements(collector)
    report = microstructure_walkforward.report(observations, settlements)
    report['canonical_execution_rows'] = len(execution_rows)
    report['canonical_execution_rejected_rows'] = len(rejected)
    report['observation_archive'] = str(observation_file)
    report['runtime_version'] = VERSION
    return report


def install(collector):
    if getattr(collector, '_MICROSTRUCTURE_RUNTIME_INSTALLED', False):
        return getattr(collector, 'MICROSTRUCTURE_RUNTIME_STATE', {})

    original_decision = collector.production_decision
    original_forward_observe = getattr(collector, 'forward_observe', None)
    symbols = tuple(getattr(collector, 'ON_DEMAND_SYMBOLS', ()) or ())
    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    observation_file = data_dir / 'microstructure_observations.jsonl'
    existing_frozen = len(microstructure_walkforward.read_observations(observation_file))

    state = {
        'enabled': True,
        'version': VERSION,
        'shadow_only': True,
        'gate_mode': 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED',
        'can_override_production': False,
        'production_decision_mutation_allowed': False,
        'observation_archive': str(observation_file),
        'frozen_signal_observations': existing_frozen,
        'research_observations_included': 0,
        'memory_by_symbol': {},
        'memory_refreshes': 0,
        'walkforward_refreshes': 0,
        'last_memory_started_at': None,
        'last_memory_finished_at': None,
        'last_walkforward_started_at': None,
        'last_walkforward_finished_at': None,
        'last_memory_error': None,
        'last_walkforward_error': None,
        'walk_forward_report': {
            'version': microstructure_walkforward.VERSION,
            'status': 'COLLECTING',
            'evidence_supports_future_gate': False,
            'gate_promoted': False,
            'gate_mode': 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED',
            'blockers': ['WAITING_FOR_BACKGROUND_MICROSTRUCTURE_WALK_FORWARD_REFRESH'],
            'frozen_observations': existing_frozen,
            'research_samples_included': False,
            'shadow_only': True,
            'can_override_production': False,
        },
    }
    lock = threading.RLock()
    observation_lock = threading.RLock()

    def _now_iso():
        return collector.now_iso() if hasattr(collector, 'now_iso') else None

    def refresh_memory():
        state['last_memory_started_at'] = _now_iso()
        try:
            rows = collector.read_all()
            now_ms = int(time.time() * 1000)
            results = {}
            for symbol in symbols:
                normalized = str(symbol).upper().replace('BINANCE:', '')
                results[normalized] = microstructure_memory.analyze(
                    normalized, rows, now_ms=now_ms
                )
            with lock:
                state['memory_by_symbol'] = results
                state['memory_refreshes'] += 1
                state['last_memory_error'] = None
            return results
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            with lock:
                state['last_memory_error'] = error
            return None
        finally:
            state['last_memory_finished_at'] = _now_iso()

    def refresh_walkforward():
        state['last_walkforward_started_at'] = _now_iso()
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
                    'version': microstructure_walkforward.VERSION,
                    'status': 'UNAVAILABLE',
                    'evidence_supports_future_gate': False,
                    'gate_promoted': False,
                    'gate_mode': 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED',
                    'blockers': ['MICROSTRUCTURE_WALK_FORWARD_REFRESH_ERROR'],
                    'error': error,
                    'research_samples_included': False,
                    'shadow_only': True,
                    'can_override_production': False,
                }
            return None
        finally:
            state['last_walkforward_finished_at'] = _now_iso()

    def cached_context(normalized):
        with lock:
            context = dict((state.get('memory_by_symbol') or {}).get(normalized) or {})
        if context:
            return context
        return {
            'version': microstructure_memory.VERSION,
            'symbol': normalized,
            'sampling_contract': 'HOURLY_ARCHIVE_ONLY_NO_FAKE_INTRABAR_MEMORY',
            'ready_windows': 0,
            'consensus': 'INSUFFICIENT',
            'windows': {},
            'research_only': True,
            'shadow_only': True,
            'can_override_production': False,
            'reason': 'WAITING_FOR_BACKGROUND_MICROSTRUCTURE_REFRESH',
        }

    def production_decision_with_microstructure_shadow(symbol):
        decision = original_decision(symbol)
        if not isinstance(decision, dict) or not decision.get('ok'):
            return decision
        normalized = str(decision.get('symbol') or symbol or '').upper().replace('BINANCE:', '')
        direction = decision.get('candidate_direction')
        context = cached_context(normalized)
        consensus = context.get('consensus') or 'INSUFFICIENT'
        relation = microstructure_walkforward.classify_relation(direction, consensus)
        decision['microstructure_shadow'] = {
            'version': VERSION,
            'memory': context,
            'consensus': consensus,
            'relation_to_candidate': relation,
            'gate_mode': 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED',
            'gate_promoted': False,
            'shadow_only': True,
            'can_override_production': False,
            'production_decision_unchanged': True,
            'production_actionable_decision': decision.get('actionable_decision'),
        }
        return decision

    def forward_observe_with_frozen_microstructure(payload):
        qualified = bool(
            isinstance(payload, dict)
            and payload.get('production_signal_qualified') is True
        )
        frozen = None
        if qualified:
            normalized = str(payload.get('symbol') or '').upper().replace('BINANCE:', '')
            context = cached_context(normalized)
            consensus = context.get('consensus') or 'INSUFFICIENT'
            relation = microstructure_walkforward.classify_relation(
                payload.get('direction'), consensus
            )
            frozen = {
                'schema': 'ATLAS_MICROSTRUCTURE_OBSERVATION_V1',
                'captured_at': _now_iso(),
                'symbol': normalized,
                'direction': payload.get('direction'),
                'entry': _f(payload.get('entry')),
                'score': _f(payload.get('final_score')),
                'signal_threshold': _f(
                    payload.get('signal_threshold'),
                    _f(getattr(collector, 'CLOUD_FORWARD_MIN_SCORE', None)),
                ),
                'microstructure_memory': context,
                'relation_to_signal': relation,
                'production_signal_qualified': True,
                'research_sample': False,
                'research_samples_included': False,
                'outcome_known_at_capture': False,
                'gate_mode': 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED',
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

    def memory_loop():
        time.sleep(9)
        while True:
            refresh_memory()
            time.sleep(MEMORY_REFRESH_SECONDS)

    def walkforward_loop():
        time.sleep(45)
        while True:
            refresh_walkforward()
            time.sleep(WALKFORWARD_REFRESH_SECONDS)

    collector.production_decision = production_decision_with_microstructure_shadow
    if callable(original_forward_observe):
        collector.forward_observe = forward_observe_with_frozen_microstructure
    collector.MICROSTRUCTURE_RUNTIME_STATE = state
    collector.microstructure_refresh_memory = refresh_memory
    collector.microstructure_refresh_walkforward = refresh_walkforward
    collector._MICROSTRUCTURE_RUNTIME_INSTALLED = True

    threading.Thread(
        target=memory_loop, daemon=True, name='atlas-microstructure-memory'
    ).start()
    threading.Thread(
        target=walkforward_loop, daemon=True, name='atlas-microstructure-walkforward'
    ).start()
    return state
