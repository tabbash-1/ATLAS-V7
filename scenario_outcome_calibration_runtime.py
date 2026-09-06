"""HTTP integration for ATLAS HTF scenario outcome calibration research."""

import urllib.parse

import scenario_outcome_calibration

VERSION = 'SCENARIO_OUTCOME_CALIBRATION_RUNTIME_V1'


def install(collector):
    if getattr(collector, '_SCENARIO_OUTCOME_CALIBRATION_RUNTIME_INSTALLED', False):
        return getattr(collector, 'SCENARIO_OUTCOME_CALIBRATION_RUNTIME_STATE', {})

    original_do_get = collector.Handler.do_GET
    state = {
        'enabled': True,
        'version': VERSION,
        'endpoint': '/api/scenarios/calibration',
        'auto_apply': False,
        'requests': 0,
        'last_error': None,
        'research_only': True,
        'live_execution': False,
    }

    def _rows():
        fn = getattr(collector, 'read_scenario_outcomes', None)
        if callable(fn):
            return fn() or []
        return []

    def do_get(self):
        u = urllib.parse.urlparse(self.path)
        if u.path not in ('/api/scenarios/calibration', '/api/scenarios/calibration/status'):
            return original_do_get(self)
        state['requests'] += 1
        if u.path.endswith('/status'):
            return self._json({**state})
        try:
            q = urllib.parse.parse_qs(u.query)
            horizon = int(q.get('horizon', ['12'])[0])
            rows = _rows()
            payload = scenario_outcome_calibration.calibrate(rows, horizon=horizon)
            payload['runtime'] = {'version': VERSION, 'rows_read': len(rows)}
            state['last_error'] = None
            return self._json(payload)
        except Exception as exc:
            state['last_error'] = f'{type(exc).__name__}: {exc}'
            return self._json({'error': str(exc), 'source': VERSION, 'research_only': True, 'live_execution': False}, 400)

    collector.Handler.do_GET = do_get
    collector._SCENARIO_OUTCOME_CALIBRATION_RUNTIME_INSTALLED = True
    collector.SCENARIO_OUTCOME_CALIBRATION_RUNTIME_STATE = state
    return state
