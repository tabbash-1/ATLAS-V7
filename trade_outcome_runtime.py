"""HTTP integration for ATLAS read-only trade outcome ledgers."""

import urllib.parse

import trade_outcome_ledger
import trade_path_settlement


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
        'path_requests': 0,
        'last_error': None,
    }

    def outcome_do_get(self):
        u = urllib.parse.urlparse(self.path)
        allowed = (
            '/api/outcomes/ledger', '/api/outcomes/summary',
            '/api/outcomes/path-ledger', '/api/outcomes/path-summary',
            '/api/outcomes/geometry-status',
        )
        if u.path not in allowed:
            return original_do_get(self)
        state['requests'] += 1
        try:
            q = urllib.parse.parse_qs(u.query)
            scope = q.get('scope', ['signals'])[0]
            symbol = q.get('symbol', [None])[0]
            rows = collector.read_forward()

            if u.path == '/api/outcomes/geometry-status':
                geometry_rows = trade_path_settlement.read_geometry_archive(collector)
                geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
                signal_rows = [x for x in rows if bool(x.get('champion_take'))]
                linked_signals = sum(1 for x in signal_rows if str(x.get('id') or '') in geometry_map)
                payload = {
                    'schema': 'ATLAS_TRADE_GEOMETRY_STATUS_V1',
                    'archive_rows': len(geometry_rows),
                    'signal_forward_rows': len(signal_rows),
                    'signal_rows_with_frozen_geometry': linked_signals,
                    'signal_geometry_coverage_pct': round(100 * linked_signals / len(signal_rows), 2) if signal_rows else None,
                    'freezer': getattr(collector, 'TRADE_GEOMETRY_FREEZER_STATE', {}),
                    'research_only': True,
                    'live_execution': False,
                }
            elif u.path in ('/api/outcomes/path-ledger', '/api/outcomes/path-summary'):
                state['path_requests'] += 1
                limit = int(q.get('limit', ['100'])[0])
                geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
                items = trade_path_settlement.build_path_ledger(rows, geometry_map, scope=scope, symbol=symbol, limit=limit)
                if u.path == '/api/outcomes/path-summary':
                    payload = {
                        'schema': 'ATLAS_TRADE_PATH_SUMMARY_V1',
                        'scope': scope,
                        'symbol': symbol,
                        'overall': trade_path_settlement.summarize_path(items),
                        'methodology': 'Frozen SL/TP geometry settled from post-entry 5m candles; same-candle SL/TP conflicts are refined with 1m candles and remain ambiguous if order is still unknowable.',
                        'research_only': True,
                        'live_execution': False,
                    }
                else:
                    payload = {
                        'schema': 'ATLAS_TRADE_PATH_LEDGER_V1',
                        'scope': scope,
                        'symbol': symbol,
                        'rows': items,
                        'research_only': True,
                        'live_execution': False,
                    }
            else:
                horizon = int(q.get('horizon', ['24'])[0])
                if u.path == '/api/outcomes/summary':
                    payload = trade_outcome_ledger.summarize(rows, horizon=horizon, scope=scope)
                else:
                    limit = int(q.get('limit', ['200'])[0])
                    payload = {
                        'schema': 'ATLAS_TRADE_OUTCOME_LEDGER_V1',
                        'horizon_h': horizon,
                        'scope': scope,
                        'symbol': symbol,
                        'rows': trade_outcome_ledger.build_ledger(rows, horizon=horizon, scope=scope, symbol=symbol, limit=limit),
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
