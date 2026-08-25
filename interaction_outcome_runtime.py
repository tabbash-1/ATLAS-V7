"""Background-only runtime for preregistered ATLAS interaction validation.

Safety sequence on every refresh:
1. refresh outcome-free Edge/Joint design,
2. refresh/freeze the persistent protocol,
3. refresh/freeze the immutable H1 rule manifest,
4. refresh the hash-bound validator guard,
5. read frozen Profit/Microstructure/Volatility sidecars,
6. run outcome-free Preflight,
7. ONLY when Preflight explicitly allows outcome access, read canonical TP/SL
   settlements and run the preregistered outcome validator.

This runtime never wraps Production decisions or Forward capture and cannot
promote a gate. All failures remain isolated to Research state.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import edge_evidence_interaction_outcome_validator as outcome_validator
import edge_evidence_interaction_preflight as preflight
import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as interaction_rules
import edge_evidence_interaction_validator_guard as validator_guard
import execution_outcome_scope
import microstructure_walkforward
import profit_engine_walkforward
import trade_path_settlement
import volatility_walkforward

VERSION = 'INTERACTION_OUTCOME_RUNTIME_V1_PREFLIGHT_GATED_BACKGROUND_ONLY'
REFRESH_SECONDS = 900
STARTUP_DELAY_SECONDS = 75


def _frozen_sidecars(collector):
    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    return {
        'profit': data_dir / 'profit_engine_observations.jsonl',
        'microstructure': data_dir / 'microstructure_observations.jsonl',
        'volatility': data_dir / 'volatility_forecast_observations.jsonl',
    }


def _read_frozen_rows(sidecars):
    return (
        profit_engine_walkforward.read_observations(sidecars['profit']),
        microstructure_walkforward.read_observations(sidecars['microstructure']),
        volatility_walkforward.read_observations(sidecars['volatility']),
    )


def _canonical_settlements(collector):
    """Canonical execution settlements. Must only be called after Preflight READY."""
    rows = collector.read_forward()
    geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
    execution_rows, rejected = execution_outcome_scope.filter_execution_rows(rows, geometry_map)
    settlements = trade_path_settlement.build_path_ledger(
        execution_rows, geometry_map, scope='all', limit=500
    )
    return settlements, execution_rows, rejected


def _governance(collector):
    # Edge report owns outcome-free joint coverage. Refresh it before evaluating
    # the frozen protocol, rules and guard. Every installer below is read-only.
    refresh_edge = getattr(collector, 'edge_evidence_refresh', None)
    if callable(refresh_edge):
        refresh_edge()

    protocol.install(collector)
    refresh_protocol = getattr(collector, 'edge_evidence_interaction_protocol_refresh', None)
    if callable(refresh_protocol):
        refresh_protocol()

    interaction_rules.install(collector)
    refresh_rules = getattr(collector, 'edge_evidence_interaction_rules_refresh', None)
    if callable(refresh_rules):
        refresh_rules()

    validator_guard.install(collector)
    refresh_guard = getattr(collector, 'edge_evidence_interaction_validator_guard_refresh', None)
    if callable(refresh_guard):
        refresh_guard()

    protocol_state = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE', {})
    rules_state = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_RULES_STATE', {})
    guard_state = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE', {})
    return (
        protocol_state.get('manifest') if isinstance(protocol_state, dict) else None,
        guard_state.get('report') if isinstance(guard_state, dict) else None,
        rules_state.get('manifest') if isinstance(rules_state, dict) else None,
    )


def build_report(collector, canonical_loader=None):
    """Build one research report. Canonical outcomes are inaccessible pre-READY."""
    protocol_manifest, guard_report, rules_manifest = _governance(collector)
    sidecars = _frozen_sidecars(collector)
    profit_rows, micro_rows, volatility_rows = _read_frozen_rows(sidecars)

    preflight_report = preflight.evaluate(
        protocol_manifest,
        guard_report,
        rules_manifest,
        profit_rows,
        micro_rows,
        volatility_rows,
    )

    base = {
        'version': VERSION,
        'background_only': True,
        'shadow_only': True,
        'research_only': True,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'gate_promoted': False,
        'sidecars': {k: str(v) for k, v in sidecars.items()},
        'preflight': preflight_report,
    }

    # Critical safety barrier: do not even call the canonical outcome loader until
    # the outcome-free frozen cohort has passed every preregistered sample minimum.
    if preflight_report.get('outcome_access_allowed') is not True:
        return {
            **base,
            'status': preflight_report.get('status') or 'COLLECTING_PRE_OUTCOME',
            'canonical_outcome_loader_called': False,
            'outcomes_read': False,
            'outcome_validation': None,
            'blockers': list(preflight_report.get('blockers') or []),
        }

    loader = canonical_loader or (lambda: _canonical_settlements(collector))
    canonical = loader()
    if not isinstance(canonical, tuple) or len(canonical) != 3:
        return {
            **base,
            'status': 'UNAVAILABLE',
            'canonical_outcome_loader_called': True,
            'outcomes_read': False,
            'outcome_validation': None,
            'blockers': ['CANONICAL_OUTCOME_LOADER_INVALID_RESULT'],
        }

    settlements, execution_rows, rejected = canonical
    validation = outcome_validator.validate(
        protocol_manifest,
        guard_report,
        rules_manifest,
        profit_rows,
        micro_rows,
        volatility_rows,
        lambda: settlements,
    )
    return {
        **base,
        'status': validation.get('status') or 'UNAVAILABLE',
        'canonical_outcome_loader_called': True,
        'outcomes_read': bool(validation.get('outcomes_read')),
        'canonical_execution_rows': len(execution_rows),
        'canonical_execution_rejected_rows': len(rejected),
        'outcome_validation': validation,
        'blockers': list(validation.get('blockers') or []),
    }


def install(collector):
    if getattr(collector, '_INTERACTION_OUTCOME_RUNTIME_INSTALLED', False):
        return getattr(collector, 'INTERACTION_OUTCOME_RUNTIME_STATE', {})

    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    state = {
        'enabled': True,
        'version': VERSION,
        'background_only': True,
        'shadow_only': True,
        'research_only': True,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'gate_promoted': False,
        'refreshes': 0,
        'last_started_at': None,
        'last_finished_at': None,
        'last_error': None,
        'report': {
            'version': VERSION,
            'status': 'COLLECTING_PRE_OUTCOME',
            'canonical_outcome_loader_called': False,
            'outcomes_read': False,
            'can_override_production': False,
            'gate_promoted': False,
            'blockers': ['WAITING_FOR_BACKGROUND_INTERACTION_PREFLIGHT'],
        },
    }
    lock = threading.RLock()

    def _now_iso():
        return collector.now_iso() if hasattr(collector, 'now_iso') else None

    def refresh():
        state['last_started_at'] = _now_iso()
        try:
            result = build_report(collector)
            with lock:
                state['report'] = result
                state['refreshes'] += 1
                state['last_error'] = None
            return result
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            unavailable = {
                'version': VERSION,
                'status': 'UNAVAILABLE',
                'background_only': True,
                'shadow_only': True,
                'research_only': True,
                'canonical_outcome_loader_called': False,
                'outcomes_read': False,
                'wraps_production_decision': False,
                'wraps_forward_observe': False,
                'can_override_production': False,
                'gate_promoted': False,
                'blockers': ['INTERACTION_OUTCOME_RUNTIME_REFRESH_ERROR'],
                'error': error,
            }
            with lock:
                state['report'] = unavailable
                state['last_error'] = error
            return None
        finally:
            state['last_finished_at'] = _now_iso()

    def loop():
        time.sleep(STARTUP_DELAY_SECONDS)
        while True:
            refresh()
            time.sleep(REFRESH_SECONDS)

    collector.INTERACTION_OUTCOME_RUNTIME_STATE = state
    collector.interaction_outcome_refresh = refresh
    collector._INTERACTION_OUTCOME_RUNTIME_INSTALLED = True

    # Install/refresh governance once at startup, still without reading outcomes.
    try:
        _governance(collector)
    except Exception as exc:
        state['last_error'] = f'{type(exc).__name__}: {exc}'

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('interaction outcome runtime mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('interaction outcome runtime mutated forward_observe')

    threading.Thread(
        target=loop, daemon=True, name='atlas-interaction-outcome-runtime'
    ).start()
    return state
