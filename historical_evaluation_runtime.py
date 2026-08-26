"""Background-only runtime for preregistered historical microstructure evaluation.

Installation occurs only after the immutable protocol has reached PREREGISTERED.
The HTTP endpoint is cached-only: GET never calls refresh(), read_forward(), or
any outcome loader.
"""
from __future__ import annotations

import copy
import threading
import time
import urllib.parse

import historical_microstructure_evaluator

VERSION = 'ATLAS_HISTORICAL_EVALUATION_RUNTIME_V1_BACKGROUND_ONLY'
REFRESH_SECONDS = 900

STATE = {
    'enabled': True,
    'background_only': True,
    'cached_only': True,
    'research_only': True,
    'live_execution': False,
    'installed': False,
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
    if STATE.get('installed'):
        return STATE
    STATE['installed'] = True
    collector.HISTORICAL_EVALUATION_RUNTIME_STATE = STATE

    original = collector.Handler.do_GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/api/research/historical-evaluation':
            # No refresh or collector reads on the request path.
            return self._json({
                'ok': STATE.get('report') is not None and STATE.get('last_error') is None,
                'version': VERSION,
                'cached_only': True,
                'background_refresh_triggered': False,
                'research_only': True,
                'live_execution': False,
                'can_override_production': False,
                'outcome_read_triggered_by_request': False,
                'runtime': {k: STATE.get(k) for k in ('enabled','background_only','refreshes','last_error','last_started_at','last_finished_at')},
                'evaluation': copy.deepcopy(STATE.get('report')),
            })
        return original(self)
    collector.Handler.do_GET = do_GET

    def loop():
        # Protocol is already preregistered before install() is called. Give the
        # process a short settle period, then evaluate only in this thread.
        time.sleep(3)
        while True:
            refresh(collector)
            time.sleep(REFRESH_SECONDS)

    threading.Thread(target=loop, daemon=True, name='atlas-historical-evaluation-runtime').start()
    return STATE
