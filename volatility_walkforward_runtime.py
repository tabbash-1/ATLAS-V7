"""Background-only runtime for ATLAS volatility walk-forward reporting.

This module does not wrap Production decisions or Forward capture. It only reads
the already-frozen volatility sidecar and later canonical TP/SL settlements in a
background loop. Failures are isolated to an UNAVAILABLE research report.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import execution_outcome_scope
import trade_path_settlement
import volatility_walkforward

VERSION = 'VOLATILITY_WALKFORWARD_RUNTIME_V1_BACKGROUND_ONLY'
REFRESH_SECONDS = 900


def _execution_settlements(collector):
    rows = collector.read_forward()
    geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
    execution_rows, rejected = execution_outcome_scope.filter_execution_rows(rows, geometry_map)
    settlements = trade_path_settlement.build_path_ledger(
        execution_rows, geometry_map, scope='all', limit=500
    )
    return settlements, execution_rows, rejected


def build_report(collector, observation_file):
    observations = volatility_walkforward.read_observations(observation_file)
    settlements, execution_rows, rejected = _execution_settlements(collector)
    report = volatility_walkforward.report(observations, settlements)
    report['canonical_execution_rows'] = len(execution_rows)
    report['canonical_execution_rejected_rows'] = len(rejected)
    report['observation_archive'] = str(observation_file)
    report['runtime_version'] = VERSION
    return report


def install(collector):
    if getattr(collector, '_VOLATILITY_WALKFORWARD_RUNTIME_INSTALLED', False):
        return getattr(collector, 'VOLATILITY_WALKFORWARD_RUNTIME_STATE', {})

    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    observation_file = data_dir / 'volatility_forecast_observations.jsonl'
    state = {
        'enabled': True,
        'version': VERSION,
        'background_only': True,
        'shadow_only': True,
        'can_override_production': False,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'observation_archive': str(observation_file),
        'refreshes': 0,
        'last_started_at': None,
        'last_finished_at': None,
        'last_error': None,
        'report': {
            'version': volatility_walkforward.VERSION,
            'status': 'COLLECTING',
            'horizons_supporting_future_filter': [],
            'chosen_trade_horizon_assumed': False,
            'gate_promoted': False,
            'gate_mode': 'OBSERVE_ONLY',
            'can_override_production': False,
            'blockers': ['WAITING_FOR_BACKGROUND_VOLATILITY_WALK_FORWARD_REFRESH'],
        },
    }
    lock = threading.RLock()

    def _now_iso():
        return collector.now_iso() if hasattr(collector, 'now_iso') else None

    def refresh():
        state['last_started_at'] = _now_iso()
        try:
            result = build_report(collector, observation_file)
            with lock:
                state['report'] = result
                state['refreshes'] += 1
                state['last_error'] = None
            return result
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            with lock:
                state['last_error'] = error
                state['report'] = {
                    'version': volatility_walkforward.VERSION,
                    'status': 'UNAVAILABLE',
                    'horizons_supporting_future_filter': [],
                    'chosen_trade_horizon_assumed': False,
                    'gate_promoted': False,
                    'gate_mode': 'OBSERVE_ONLY',
                    'can_override_production': False,
                    'blockers': ['VOLATILITY_WALK_FORWARD_REFRESH_ERROR'],
                    'error': error,
                }
            return None
        finally:
            state['last_finished_at'] = _now_iso()

    def loop():
        time.sleep(55)
        while True:
            refresh()
            time.sleep(REFRESH_SECONDS)

    collector.VOLATILITY_WALKFORWARD_RUNTIME_STATE = state
    collector.volatility_refresh_walkforward = refresh
    collector._VOLATILITY_WALKFORWARD_RUNTIME_INSTALLED = True
    threading.Thread(
        target=loop, daemon=True, name='atlas-volatility-walkforward'
    ).start()
    return state
