"""HTTP integration for ATLAS read-only trade outcome ledgers."""

import json
import threading
import time
import urllib.parse

import trade_outcome_ledger
import trade_path_settlement

SETTLEMENT_INTERVAL_SECONDS = 900


def _repair_null_forward_slots(collector):
    """Repair legacy rows where None-valued horizon keys permanently block maturation.

    collector.update_forward_returns() historically skips a horizon whenever the
    key already exists. Older rows can therefore get stuck forever when a key was
    persisted as null. Remove only null placeholders; never rewrite real returns.
    """
    rows = collector.read_forward()
    changed = 0
    for row in rows:
        fr = row.get('forward_return_pct')
        if not isinstance(fr, dict):
            row['forward_return_pct'] = {}
            changed += 1
            continue
        for key in ('1', '4', '12', '24'):
            if key in fr and fr.get(key) is None:
                del fr[key]
                changed += 1
    if not changed:
        return 0

    archive = getattr(collector, 'FORWARD_ARCHIVE', None)
    if archive is None:
        return 0
    tmp = archive.with_suffix('.tmp')
    lock = getattr(collector, 'ARCHIVE_LOCK', None)

    def write_rows():
        with tmp.open('w') as handle:
            for row in rows:
                handle.write(json.dumps(row, separators=(',', ':')) + '\n')
        tmp.replace(archive)

    if lock is None:
        write_rows()
    else:
        with lock:
            write_rows()
    return changed


def _settle_forward_maturity(collector):
    """Retry canonical forward maturation and return a compact audit record."""
    repaired = _repair_null_forward_slots(collector)
    result = collector.update_forward_returns()
    if not isinstance(result, dict):
        result = {'updated': 0, 'rows': len(collector.read_forward())}
    return {
        'repaired_null_slots': repaired,
        'updated_returns': int(result.get('updated') or 0),
        'rows': int(result.get('rows') or len(collector.read_forward())),
    }


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
        'settlement_runs': 0,
        'settlement_updates': 0,
        'settlement_repairs': 0,
        'last_settlement_started_at': None,
        'last_settlement_finished_at': None,
        'last_settlement_error': None,
        'last_error': None,
        'signal_scope_semantics': 'PRODUCTION_QUALIFIED_ONLY',
    }
    settlement_lock = threading.Lock()

    def settle_once():
        if not settlement_lock.acquire(blocking=False):
            return {'skipped': True, 'reason': 'SETTLEMENT_ALREADY_RUNNING'}
        state['last_settlement_started_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
        try:
            result = _settle_forward_maturity(collector)
            state['settlement_runs'] += 1
            state['settlement_updates'] += int(result.get('updated_returns') or 0)
            state['settlement_repairs'] += int(result.get('repaired_null_slots') or 0)
            state['last_settlement_error'] = None
            return result
        except Exception as exc:
            state['last_settlement_error'] = f'{type(exc).__name__}: {exc}'
            return {'error': state['last_settlement_error']}
        finally:
            state['last_settlement_finished_at'] = collector.now_iso() if hasattr(collector, 'now_iso') else None
            settlement_lock.release()

    def settlement_loop():
        # Give boot/deploy a short head start, then independently mature outcomes.
        time.sleep(15)
        while True:
            settle_once()
            time.sleep(SETTLEMENT_INTERVAL_SECONDS)

    def scoped_rows(rows, scope):
        scope = str(scope or 'signals').lower()
        if scope == 'signals':
            return [x for x in rows if trade_outcome_ledger.is_production_signal(x)]
        if scope == 'champions':
            return [x for x in rows if trade_outcome_ledger.is_research_champion(x)]
        if scope == 'all':
            return list(rows)
        raise ValueError('scope must be signals, champions or all')

    def outcome_do_get(self):
        u = urllib.parse.urlparse(self.path)
        allowed = (
            '/api/outcomes/ledger', '/api/outcomes/summary',
            '/api/outcomes/path-ledger', '/api/outcomes/path-summary',
            '/api/outcomes/geometry-status', '/api/outcomes/settlement-status',
        )
        if u.path not in allowed:
            return original_do_get(self)
        state['requests'] += 1
        try:
            q = urllib.parse.parse_qs(u.query)
            scope = q.get('scope', ['signals'])[0]
            symbol = q.get('symbol', [None])[0]

            if u.path == '/api/outcomes/settlement-status':
                payload = {'schema': 'ATLAS_OUTCOME_SETTLEMENT_STATUS_V1', **state, 'research_only': True, 'live_execution': False}
                return self._json(payload)

            # Outcome reads are self-healing: before reporting OPEN rows, retry
            # any matured forward labels. This removes the old dependency on the
            # hourly cloud-forward cycle and prevents day-old signals staying OPEN.
            settle_once()
            rows = collector.read_forward()

            if u.path == '/api/outcomes/geometry-status':
                geometry_rows = trade_path_settlement.read_geometry_archive(collector)
                geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
                signal_rows = [x for x in rows if trade_outcome_ledger.is_production_signal(x)]
                linked_signals = sum(1 for x in signal_rows if str(x.get('id') or '') in geometry_map)
                research_champions = [x for x in rows if trade_outcome_ledger.is_research_champion(x)]
                payload = {
                    'schema': 'ATLAS_TRADE_GEOMETRY_STATUS_V1',
                    'archive_rows': len(geometry_rows),
                    'production_signal_forward_rows': len(signal_rows),
                    'research_champion_forward_rows': len(research_champions),
                    'signal_forward_rows': len(signal_rows),
                    'signal_rows_with_frozen_geometry': linked_signals,
                    'signal_geometry_coverage_pct': round(100 * linked_signals / len(signal_rows), 2) if signal_rows else None,
                    'signal_scope_semantics': 'PRODUCTION_QUALIFIED_ONLY',
                    'freezer': getattr(collector, 'TRADE_GEOMETRY_FREEZER_STATE', {}),
                    'research_only': True,
                    'live_execution': False,
                }
            elif u.path in ('/api/outcomes/path-ledger', '/api/outcomes/path-summary'):
                state['path_requests'] += 1
                limit = int(q.get('limit', ['100'])[0])
                geometry_map = trade_path_settlement.geometry_by_forward_id(collector)
                selected_rows = scoped_rows(rows, scope)
                items = trade_path_settlement.build_path_ledger(selected_rows, geometry_map, scope='all', symbol=symbol, limit=limit)
                if u.path == '/api/outcomes/path-summary':
                    payload = {
                        'schema': 'ATLAS_TRADE_PATH_SUMMARY_V1',
                        'scope': scope,
                        'symbol': symbol,
                        'signal_scope_semantics': 'PRODUCTION_QUALIFIED_ONLY' if scope == 'signals' else None,
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
                        'signal_scope_semantics': 'PRODUCTION_QUALIFIED_ONLY' if scope == 'signals' else None,
                        'rows': items,
                        'research_only': True,
                        'live_execution': False,
                    }
            else:
                horizon = int(q.get('horizon', ['24'])[0])
                if u.path == '/api/outcomes/summary':
                    payload = trade_outcome_ledger.summarize(rows, horizon=horizon, scope=scope)
                    payload['settlement_status'] = {
                        'runs': state['settlement_runs'],
                        'updated_returns': state['settlement_updates'],
                        'repaired_null_slots': state['settlement_repairs'],
                        'last_error': state['last_settlement_error'],
                    }
                else:
                    limit = int(q.get('limit', ['200'])[0])
                    payload = {
                        'schema': 'ATLAS_TRADE_OUTCOME_LEDGER_V1',
                        'horizon_h': horizon,
                        'scope': scope,
                        'symbol': symbol,
                        'rows': trade_outcome_ledger.build_ledger(rows, horizon=horizon, scope=scope, symbol=symbol, limit=limit),
                        'settlement_status': {
                            'runs': state['settlement_runs'],
                            'updated_returns': state['settlement_updates'],
                            'repaired_null_slots': state['settlement_repairs'],
                            'last_error': state['last_settlement_error'],
                        },
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
    collector.outcome_settle_once = settle_once
    threading.Thread(target=settlement_loop, daemon=True, name='atlas-outcome-settlement').start()
    return state
