"""HTTP integration for ATLAS outcome calibration research."""

import urllib.parse

import outcome_calibration

VERSION = 'OUTCOME_CALIBRATION_RUNTIME_V1'


def install(collector):
    if getattr(collector, '_OUTCOME_CALIBRATION_RUNTIME_INSTALLED', False):
        return getattr(collector, 'OUTCOME_CALIBRATION_RUNTIME_STATE', {})

    original_do_get = collector.Handler.do_GET
    state = {
        'enabled': True,
        'version': VERSION,
        'endpoint': '/api/outcomes/calibration',
        'threshold_auto_apply': False,
        'requests': 0,
        'last_error': None,
        'research_only': True,
    }

    def do_get(self):
        u = urllib.parse.urlparse(self.path)
        if u.path not in ('/api/outcomes/calibration', '/api/outcomes/calibration/status'):
            return original_do_get(self)
        state['requests'] += 1
        if u.path.endswith('/status'):
            return self._json({**state, 'live_execution': False})
        try:
            q = urllib.parse.parse_qs(u.query)
            horizon = int(q.get('horizon', ['24'])[0])
            threshold = float(q.get('threshold', [str(getattr(collector, 'CLOUD_FORWARD_MIN_SCORE', 68))])[0])
            # Mature any eligible canonical forward returns before calibration.
            settle = getattr(collector, 'outcome_settle_once', None)
            if callable(settle):
                settle()
            rows = collector.read_forward()
            payload = outcome_calibration.calibrate(rows, horizon=horizon, current_threshold=threshold)
            payload['runtime'] = {'version': VERSION, 'rows_read': len(rows)}
            state['last_error'] = None
            return self._json(payload)
        except Exception as exc:
            state['last_error'] = f'{type(exc).__name__}: {exc}'
            return self._json({'error': str(exc), 'source': VERSION, 'research_only': True, 'live_execution': False}, 400)

    collector.Handler.do_GET = do_get
    collector._OUTCOME_CALIBRATION_RUNTIME_INSTALLED = True
    collector.OUTCOME_CALIBRATION_RUNTIME_STATE = state
    return state
