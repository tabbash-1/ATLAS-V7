"""Read-only cached HTTP surface for ATLAS interaction-validation state.

GET /api/research/interaction-status returns only the latest background-cached
INTERACTION_OUTCOME_RUNTIME_STATE. The request path never refreshes governance,
reads frozen sidecars, reads Forward rows, settles TP/SL paths, or runs validators.
"""

from __future__ import annotations

from copy import deepcopy
import urllib.parse

VERSION = 'INTERACTION_STATUS_API_V1_CACHED_READ_ONLY'
PATH = '/api/research/interaction-status'


def _cached_payload(collector):
    state = getattr(collector, 'INTERACTION_OUTCOME_RUNTIME_STATE', None)
    if not isinstance(state, dict):
        return {
            'version': VERSION,
            'status': 'UNAVAILABLE',
            'cached_only': True,
            'background_refresh_triggered': False,
            'canonical_outcome_loader_called_by_request': False,
            'outcomes_read_by_request': False,
            'research_only': True,
            'can_override_production': False,
            'gate_promoted': False,
            'blockers': ['INTERACTION_OUTCOME_RUNTIME_NOT_INSTALLED'],
        }

    report = deepcopy(state.get('report')) if isinstance(state.get('report'), dict) else {}
    preflight = report.get('preflight') if isinstance(report.get('preflight'), dict) else None
    return {
        'version': VERSION,
        'status': report.get('status') or 'UNAVAILABLE',
        'cached_only': True,
        'background_refresh_triggered': False,
        'canonical_outcome_loader_called_by_request': False,
        'outcomes_read_by_request': False,
        'runtime': {
            'version': state.get('version'),
            'enabled': bool(state.get('enabled')),
            'background_only': bool(state.get('background_only')),
            'shadow_only': bool(state.get('shadow_only')),
            'research_only': bool(state.get('research_only', True)),
            'refreshes': int(state.get('refreshes') or 0),
            'last_started_at': state.get('last_started_at'),
            'last_finished_at': state.get('last_finished_at'),
            'last_error': state.get('last_error'),
        },
        'preflight': deepcopy(preflight),
        'canonical_outcome_loader_called_in_background': bool(report.get('canonical_outcome_loader_called')),
        'outcomes_read_in_background': bool(report.get('outcomes_read')),
        'outcome_validation': deepcopy(report.get('outcome_validation')) if isinstance(report.get('outcome_validation'), dict) else None,
        'research_only': True,
        'can_override_production': False,
        'gate_promoted': False,
        'blockers': list(report.get('blockers') or []),
    }


def install(collector):
    """Install a single cached GET endpoint without mutating decision functions."""
    if getattr(collector, '_INTERACTION_STATUS_API_INSTALLED', False):
        return {'enabled': True, 'version': VERSION, 'path': PATH, 'cached_only': True}

    handler = getattr(collector, 'Handler', None)
    if handler is None or not hasattr(handler, 'do_GET'):
        raise RuntimeError('collector Handler.do_GET unavailable')

    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    original_get = handler.do_GET

    def cached_interaction_status_get(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == PATH:
            return self._json(_cached_payload(collector), 200)
        return original_get(self)

    handler.do_GET = cached_interaction_status_get
    collector.interaction_status_cached_payload = lambda: _cached_payload(collector)
    collector._INTERACTION_STATUS_API_INSTALLED = True

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('interaction status API mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('interaction status API mutated forward_observe')

    return {
        'enabled': True,
        'version': VERSION,
        'path': PATH,
        'cached_only': True,
        'background_refresh_triggered_by_request': False,
        'canonical_outcome_loader_called_by_request': False,
        'outcomes_read_by_request': False,
        'can_override_production': False,
        'gate_promoted': False,
    }
