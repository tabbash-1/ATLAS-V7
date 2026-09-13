import json
from types import SimpleNamespace

from staged_shadow_api_overlay import API_PATH, install


class FakeHandler:
    last = None
    path = API_PATH + '?symbol=BTCUSDT'

    def _json(self, payload, status=200):
        FakeHandler.last = (payload, status)
        return payload

    def do_GET(self):
        return {'fallback': True}


def test_overlay_does_not_wrap_or_replace_production_decision():
    def production_decision(symbol):
        return {
            'ok': True,
            'symbol': symbol,
            'candidate_direction': 'LONG',
            'product_direction': 'LONG',
            'entry_confirmation_direction': 'LONG',
            'direction_alignment': 'ALIGNED',
            'entry': 100,
            'stop_loss': 98,
            'tp1': 102,
            'tp2': 104,
            'final_trade_gate': {
                'status': 'TRADE_READY',
                'trade_ready': True,
                'product_direction': 'LONG',
                'entry_confirmation_direction': 'LONG',
                'direction_alignment': 'ALIGNED',
            },
            'canonical_decision': {'decision': 'LONG', 'source_of_truth': 'FINAL_TRADE_GATE'},
        }

    atlas = SimpleNamespace(Handler=FakeHandler, production_decision=production_decision)
    original_callable = atlas.production_decision
    state = install(atlas)
    assert atlas.production_decision is original_callable
    assert state['can_override_production'] is False
    h = FakeHandler()
    payload = h.do_GET()
    assert payload['ok'] is True
    assert payload['production_decision_callable_unchanged'] is True
    assert atlas.production_decision is original_callable
    assert payload['canonical_decision']['decision'] == 'LONG'


def test_overlay_is_idempotent():
    atlas = SimpleNamespace(Handler=FakeHandler, production_decision=lambda symbol: {'ok': False, 'symbol': symbol})
    first = install(atlas)
    second = install(atlas)
    assert first['version'] == second['version']
    assert second['shadow_only'] is True
