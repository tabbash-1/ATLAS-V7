import types

import production_execution_semantics_overlay as overlay


def make_handler_class():
    class Handler:
        def __init__(self):
            self.sent = None

        def _json(self, payload, status=200):
            self.sent = (payload, status)
            return payload

    return Handler


def install_handler():
    # Each test gets a brand-new Handler class. The overlay monkey-patches
    # Handler._json, so reusing one global class would stack wrappers across
    # tests and corrupt the legacy geometry_ready input.
    atlas = types.SimpleNamespace(Handler=make_handler_class())
    overlay.install(atlas)
    return atlas


def test_geometry_without_explicit_permission_stays_wait():
    atlas = install_handler(); h = atlas.Handler()
    payload = {
        'ok': True, 'source': 'PRODUCTION_DECISION_API_TEST',
        'signal_qualified': True, 'candidate_direction': 'LONG',
        'execution_ready': True, 'trade_plan': {'can_execute': False},
        'geometry_gate': {'qualified': True},
    }
    h._json(payload)
    out = h.sent[0]
    assert out['geometry_ready'] is True
    assert out['execution_permission_ready'] is False
    assert out['execution_ready'] is False
    assert out['actionable_decision'] == 'WAIT'
    assert out['actionable_reason'] == 'EXECUTION_TRIGGER_OR_PERMISSION_PENDING'


def test_explicit_permission_can_be_execution_ready():
    atlas = install_handler(); h = atlas.Handler()
    payload = {
        'ok': True, 'source': 'PRODUCTION_DECISION_API_TEST',
        'signal_qualified': True, 'candidate_direction': 'SHORT',
        'execution_ready': True, 'trade_plan': {'can_execute': True},
    }
    h._json(payload)
    out = h.sent[0]
    assert out['geometry_ready'] is True
    assert out['execution_permission_ready'] is True
    assert out['execution_ready'] is True
    assert out['actionable_decision'] == 'SHORT'
    assert out['execution_contract']['rule'].endswith('can_execute=true')


def test_permission_cannot_bypass_bad_geometry():
    atlas = install_handler(); h = atlas.Handler()
    payload = {
        'ok': True, 'source': 'PRODUCTION_DECISION_API_TEST',
        'signal_qualified': True, 'candidate_direction': 'LONG',
        'execution_ready': False, 'trade_plan': {'can_execute': True},
        'geometry_gate': {'reason': 'BAD_GEOMETRY'},
    }
    h._json(payload)
    out = h.sent[0]
    assert out['geometry_ready'] is False
    assert out['execution_ready'] is False
    assert out['actionable_decision'] == 'WAIT'


def test_threshold_and_score_are_untouched():
    atlas = install_handler(); h = atlas.Handler()
    payload = {
        'ok': True, 'source': 'PRODUCTION_DECISION_API_TEST',
        'signal_qualified': True, 'candidate_direction': 'LONG',
        'score': 72, 'signal_threshold': 68,
        'execution_ready': True, 'trade_plan': {'can_execute': False},
    }
    h._json(payload)
    out = h.sent[0]
    assert out['score'] == 72
    assert out['signal_threshold'] == 68
    assert out['candidate_direction'] == 'LONG'
