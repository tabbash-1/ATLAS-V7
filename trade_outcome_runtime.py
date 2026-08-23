"""HTTP integration for the read-only ATLAS trade outcome ledger."""

import urllib.parse

import trade_outcome_ledger


def install(collector):
    if getattr(collector, '_TRADE_OUTCOME_RUNTIME_INSTALLED', False):
        return getattr(collector, 'TRADE_OUTCOME_RUNTIME_STATE', {})

    original_do_get = collector.Handler.do_GET
    state = {
        'enabled': True,
        'read_only': True,
        'default_scope': 'signals',
        'default_horizon_h': 24,
        'requests': 0,
        'last_error': None,
    }

    def outcome_do_get(self):
        u = urllib.parse.urlparse(self.path)
        if u.path not in ('/api/outcomes/ledger', '/api/outcomes/summary'):
            return original_do_get(self)
        state['requests'] += 1
        try:
            q = urllib.parse.parse_qs(u.query)
            horizon = int(q.get('horizon', ['24'])[0])
            scope = q.get('scope', ['signals'])[0]
            symbol = q.get('symbol', [None])[0]
            rows = collector.read_forward()
            if u.path == '/api/outcomes/summary':
                payload = trade_outcome_ledger.summarize(rows, horizon=horizon, scope=scope)
            else:
                limit = int(q.get('limit', ['200'])[0])
                payload = {
                    'schema': 'ATLAS_TRADE_OUTCOME_LEDGER_V1',
                    'horizon_h': horizon,
                    'scope': scope,
                    'symbol': symbol,
                    'rows': trade_outcome_ledger.build_ledger(
                        rows, horizon=horizon, scope=scope, symbol=symbol, limit=limit
                    ),
                    'research_only': True,
                    'live_execution': False,
                }
            state['last_error'] = None
            return self._json(payload)
        except Exception as exc:
            state['last_error'] = f'{type(exc).__name__}: {exc}'
            return self._json({'error': str(exc), 'research_only': True}, 400)

    collector.Handler.do_GET = outcome_do_get
    collector.TRADE_OUTCOME_RUNTIME_STATE = state
    collector._TRADE_OUTCOME_RUNTIME_INSTALLED = True
    return state
