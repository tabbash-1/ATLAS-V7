from types import SimpleNamespace

import interaction_status_api as api


class DummyHandler:
    def __init__(self, path):
        self.path = path
        self.payload = None
        self.code = None
        self.original_called = False

    def _json(self, payload, code=200, headers=None):
        self.payload = payload
        self.code = code
        return payload

    def do_GET(self):
        self.original_called = True
        return 'ORIGINAL'


def collector(state=None):
    decision = lambda symbol: {'symbol': symbol, 'decision': 'WAIT'}
    forward = lambda payload: {'forward_id': 'F1'}
    attrs = {
        'Handler': DummyHandler,
        'production_decision': decision,
        'forward_observe': forward,
    }
    if state is not None:
        attrs['INTERACTION_OUTCOME_RUNTIME_STATE'] = state
    return SimpleNamespace(**attrs), decision, forward


def test_cached_endpoint_exposes_preflight_without_triggering_refresh_or_outcomes():
    state = {
        'enabled': True,
        'version': 'RUNTIME',
        'background_only': True,
        'shadow_only': True,
        'research_only': True,
        'refreshes': 2,
        'last_started_at': 'A',
        'last_finished_at': 'B',
        'last_error': None,
        'report': {
            'status': 'COLLECTING_PRE_OUTCOME',
            'canonical_outcome_loader_called': False,
            'outcomes_read': False,
            'preflight': {
                'status': 'COLLECTING_PRE_OUTCOME',
                'matched_frozen_total': 17,
                'candidate_frozen_by_horizon': {'1': 3, '4': 4, '12': 2},
                'outcome_access_allowed': False,
            },
            'outcome_validation': None,
            'blockers': ['MIN_FROZEN_COMMON_COHORT_NOT_REACHED'],
        },
    }
    c, decision, forward = collector(state)
    refresh_called = {'n': 0}
    c.interaction_outcome_refresh = lambda: refresh_called.__setitem__('n', refresh_called['n'] + 1)

    result = api.install(c)
    assert result['cached_only'] is True
    h = c.Handler(api.PATH + '?ignored=1')
    h.do_GET()
    assert h.code == 200
    assert h.payload['status'] == 'COLLECTING_PRE_OUTCOME'
    assert h.payload['cached_only'] is True
    assert h.payload['background_refresh_triggered'] is False
    assert h.payload['canonical_outcome_loader_called_by_request'] is False
    assert h.payload['outcomes_read_by_request'] is False
    assert h.payload['preflight']['matched_frozen_total'] == 17
    assert h.payload['preflight']['candidate_frozen_by_horizon']['4'] == 4
    assert h.payload['live_execution'] is False
    assert refresh_called['n'] == 0
    assert c.production_decision is decision
    assert c.forward_observe is forward


def test_cached_governance_diagnostics_do_not_refresh_any_layer():
    state = {
        'enabled': True,
        'refreshes': 1,
        'report': {'status': 'BLOCKED', 'preflight': {'status': 'BLOCKED'}, 'blockers': ['X']},
    }
    c, _, _ = collector(state)
    c.EDGE_EVIDENCE_JOINT_COVERAGE_STATE = {
        'report': {
            'status': 'COLLECTING',
            'future_interaction_validation_supported': False,
            'horizons_with_sufficient_joint_coverage_h': [4],
            'blockers': ['SPARSE'],
        }
    }
    c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE = {
        'registration_locked': False,
        'persistence_error': None,
        'manifest': {'status': 'BLOCKED_BY_DESIGN', 'protocol_hash': 'P', 'eligible_volatility_horizons_h': [], 'blockers': ['J']},
    }
    c.EDGE_EVIDENCE_INTERACTION_RULES_STATE = {
        'registration_locked': False,
        'persistence_error': None,
        'manifest': {'status': 'BLOCKED_BY_PROTOCOL', 'rules_hash': 'R', 'parent_protocol_hash': 'P', 'eligible_volatility_horizons_h': [], 'blockers': ['PARENT']},
    }
    c.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE = {
        'report': {'status': 'BLOCKED', 'armed_protocol_hash': None, 'registered_eligible_horizons_h': [], 'current_eligible_horizons_h': [4], 'blockers': ['NOT_READY']}
    }
    refreshes = {'n': 0}
    c.edge_evidence_refresh = lambda: refreshes.__setitem__('n', refreshes['n'] + 1)
    c.edge_evidence_interaction_protocol_refresh = lambda: refreshes.__setitem__('n', refreshes['n'] + 1)
    c.edge_evidence_interaction_rules_refresh = lambda: refreshes.__setitem__('n', refreshes['n'] + 1)
    c.edge_evidence_interaction_validator_guard_refresh = lambda: refreshes.__setitem__('n', refreshes['n'] + 1)

    api.install(c)
    h = c.Handler(api.PATH)
    h.do_GET()
    g = h.payload['governance']
    assert g['cached_only'] is True
    assert g['refresh_triggered_by_request'] is False
    assert g['joint_coverage']['status'] == 'COLLECTING'
    assert g['protocol']['status'] == 'BLOCKED_BY_DESIGN'
    assert g['rules']['status'] == 'BLOCKED_BY_PROTOCOL'
    assert g['guard']['status'] == 'BLOCKED'
    assert refreshes['n'] == 0


def test_missing_runtime_returns_cached_unavailable_without_refresh():
    c, _, _ = collector()
    api.install(c)
    h = c.Handler(api.PATH)
    h.do_GET()
    assert h.payload['status'] == 'UNAVAILABLE'
    assert h.payload['outcomes_read_by_request'] is False
    assert h.payload['live_execution'] is False
    assert 'INTERACTION_OUTCOME_RUNTIME_NOT_INSTALLED' in h.payload['blockers']


def test_other_routes_fall_through_to_original_handler():
    c, _, _ = collector({'report': {}})
    api.install(c)
    h = c.Handler('/health')
    out = h.do_GET()
    assert out == 'ORIGINAL'
    assert h.original_called is True


def test_payload_is_deep_copied_not_live_mutable_state():
    state = {
        'enabled': True,
        'report': {
            'status': 'COLLECTING_PRE_OUTCOME',
            'preflight': {'candidate_frozen_by_horizon': {'1': 2}},
            'blockers': [],
        },
    }
    c, _, _ = collector(state)
    api.install(c)
    payload = c.interaction_status_cached_payload()
    payload['preflight']['candidate_frozen_by_horizon']['1'] = 999
    assert state['report']['preflight']['candidate_frozen_by_horizon']['1'] == 2


def test_install_is_idempotent_and_does_not_stack_get_wrappers():
    c, decision, forward = collector({'report': {}})
    first = api.install(c)
    wrapped = c.Handler.do_GET
    second = api.install(c)
    assert first['path'] == second['path']
    assert c.Handler.do_GET is wrapped
    assert c.production_decision is decision
    assert c.forward_observe is forward
