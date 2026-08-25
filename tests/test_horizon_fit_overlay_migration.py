from pathlib import Path
import tempfile
from types import SimpleNamespace

import horizon_fit_overlay
import horizon_fit_policy
from quick_reentry_guard import QuickReentryGuard


def _decision():
    return {
        'ok': True,
        'symbol': 'BTCUSDT',
        'candidate_direction': 'LONG',
        'score': 64.0,
        'signal_threshold': 68.0,
        'direction_votes': 4,
        'relative_volume': 0.5,
        'production_signal_qualified': False,
        'execution_ready': False,
        'opportunity_state': 'WATCH',
        'risk_reward': 2.0,
        'actionable_decision': 'WAIT',
        'tactical_opportunity': {'risk_reward': 2.0},
        'structural_geometry': {'breakout': {'confirmed': False}},
        'quick_trade_shadow': {
            'status': 'QUICK_TRADE_ACTIVE',
            'direction': 'LONG',
            'reason': 'ACTIVE_SAME_DIRECTION_SIGNAL_NOT_REISSUED',
            'entry': 100,
            'stop_loss': 99,
            'target': 102,
            'risk_reward': 2.0,
            'active_remaining_seconds': 5000,
            'shadow_only': True,
            'can_override_production': False,
        },
        'timeframe_matrix': {'swing': {}},
    }


def test_overlay_rejects_unversioned_legacy_active_and_cleans_geometry():
    with tempfile.TemporaryDirectory() as td:
        guard = QuickReentryGuard(Path(td) / 'guard.json')
        guard.register('BTCUSDT', 'LONG', 100, 99, 102, score=64, now=1000)
        atlas = SimpleNamespace(production_decision=lambda symbol: _decision(), QUICK_REENTRY_GUARD=guard)
        horizon_fit_overlay.install(atlas)
        out = atlas.production_decision('BTCUSDT')
        q = out['quick_trade_shadow']
        assert out['horizon_fit_overlay_version'] == 'HORIZON_FIT_OVERLAY_V4_CLEAN_QUICK_STATE'
        assert q['status'] == 'WATCH_ONLY'
        assert q['legacy_guard_cleanup']['cancelled'] is True
        for stale in ('entry', 'stop_loss', 'target', 'risk_reward', 'active_remaining_seconds'):
            assert stale not in q
        assert out['production_threshold_changed_by_horizon_policy'] is False
        inspected = guard.inspect('BTCUSDT', 'LONG', 100, now=1001)
        assert inspected['state'] == 'POLICY_REJECTED'


def test_overlay_preserves_current_policy_active():
    with tempfile.TemporaryDirectory() as td:
        guard = QuickReentryGuard(Path(td) / 'guard.json')
        guard.register('BTCUSDT', 'LONG', 100, 99, 102, score=64, now=1000)
        guard.approve_active_policy('BTCUSDT', 'LONG', horizon_fit_policy.VERSION, now=1001)
        atlas = SimpleNamespace(production_decision=lambda symbol: _decision(), QUICK_REENTRY_GUARD=guard)
        horizon_fit_overlay.install(atlas)
        out = atlas.production_decision('BTCUSDT')
        q = out['quick_trade_shadow']
        assert q['status'] == 'QUICK_TRADE_ACTIVE'
        assert q['policy_version'] == horizon_fit_policy.VERSION
        assert q['entry'] == 100
        assert q['stop_loss'] == 99
        assert q['target'] == 102
        cleanup = q['legacy_guard_cleanup']
        assert cleanup['cancelled'] is False
        assert cleanup['reason'] == 'POLICY_VERSION_CURRENT'


if __name__ == '__main__':
    test_overlay_rejects_unversioned_legacy_active_and_cleans_geometry()
    test_overlay_preserves_current_policy_active()
    print('horizon fit overlay migration tests: ok')
