"""Background-only runtime for preregistered historical microstructure evaluation."""
from __future__ import annotations

import copy
import threading
import time

import historical_microstructure_evaluator

VERSION = 'ATLAS_HISTORICAL_EVALUATION_RUNTIME_V1_BACKGROUND_ONLY'
REFRESH_SECONDS = 900

STATE = {
    'enabled': True,
    'background_only': True,
    'cached_only': True,
    'research_only': True,
    'live_execution': False,
    'refreshes': 0,
    'last_error': None,
    'last_started_at': None,
    'last_finished_at': None,
    'report': None,
}


def refresh(collector):
    STATE['last_started_at'] = collector.now_iso()
    try:
        registry = getattr(collector, 'HISTORICAL_REPLAY_REGISTRY_STATE', {}) or {}
        protocol = getattr(collector, 'HISTORICAL_EVALUATION_PROTOCOL_STATE', {}) or {}
        STATE['report'] = historical_microstructure_evaluator.evaluate(
            registry,
            protocol,
            collector.read_forward,
        )
        STATE['refreshes'] += 1
        STATE['last_error'] = None
    except Exception as exc:
        STATE['last_error'] = f'{type(exc).__name__}: {exc}'
    finally:
        STATE['last_finished_at'] = collector.now_iso()
    return copy.deepcopy(STATE)


def install(collector):
    collector.HISTORICAL_EVALUATION_RUNTIME_STATE = STATE

    def loop():
        # Registry + protocol install asynchronously; wait until both have had
        # time to settle, then evaluate only from this background thread.
        time.sleep(30)
        while True:
            refresh(collector)
            time.sleep(REFRESH_SECONDS)

    threading.Thread(target=loop, daemon=True, name='atlas-historical-evaluation-runtime').start()
    return STATE
