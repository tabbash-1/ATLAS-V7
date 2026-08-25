from pathlib import Path
import tempfile

from quick_reentry_guard import QuickReentryGuard


def test_policy_cancel_only_cancels_active_signal():
    with tempfile.TemporaryDirectory() as td:
        guard = QuickReentryGuard(Path(td) / 'guard.json')
        guard.register('BTCUSDT', 'LONG', 100, 99, 102, risk_reward=2.0, score=64, now=1000)
        result = guard.cancel_active('BTCUSDT', 'LONG', reason='STRICT_POLICY', now=1001)
        assert result['cancelled'] is True
        inspected = guard.inspect('BTCUSDT', 'LONG', 100, now=1002)
        assert inspected['allow_new'] is True
        assert inspected['state'] == 'POLICY_REJECTED'
        again = guard.cancel_active('BTCUSDT', 'LONG', now=1003)
        assert again['cancelled'] is False


def test_strict_policy_stamp_preserves_current_active_signal():
    with tempfile.TemporaryDirectory() as td:
        guard = QuickReentryGuard(Path(td) / 'guard.json')
        guard.register('BTCUSDT', 'LONG', 100, 99, 102, risk_reward=2.0, score=66, now=1000)
        approved = guard.approve_active_policy('BTCUSDT', 'LONG', 'HORIZON_FIT_POLICY_V1', now=1001)
        assert approved['approved'] is True
        migrated = guard.reject_legacy_active('BTCUSDT', 'LONG', 'HORIZON_FIT_POLICY_V1', now=1002)
        assert migrated['cancelled'] is False
        assert migrated['reason'] == 'POLICY_VERSION_CURRENT'
        inspected = guard.inspect('BTCUSDT', 'LONG', 100, now=1003)
        assert inspected['state'] == 'ACTIVE'
        assert inspected['record']['policy_version'] == 'HORIZON_FIT_POLICY_V1'


def test_unversioned_legacy_active_is_rejected_once():
    with tempfile.TemporaryDirectory() as td:
        guard = QuickReentryGuard(Path(td) / 'guard.json')
        guard.register('BTCUSDT', 'LONG', 100, 99, 102, risk_reward=2.0, score=64, now=1000)
        migrated = guard.reject_legacy_active('BTCUSDT', 'LONG', 'HORIZON_FIT_POLICY_V1', now=1001)
        assert migrated['cancelled'] is True
        assert migrated['record']['status'] == 'POLICY_REJECTED'
        assert migrated['record']['required_policy_version'] == 'HORIZON_FIT_POLICY_V1'
        again = guard.reject_legacy_active('BTCUSDT', 'LONG', 'HORIZON_FIT_POLICY_V1', now=1002)
        assert again['cancelled'] is False
        inspected = guard.inspect('BTCUSDT', 'LONG', 100, now=1003)
        assert inspected['allow_new'] is True
        assert inspected['state'] == 'POLICY_REJECTED'


if __name__ == '__main__':
    test_policy_cancel_only_cancels_active_signal()
    test_strict_policy_stamp_preserves_current_active_signal()
    test_unversioned_legacy_active_is_rejected_once()
    print('quick reentry guard policy cancel tests: ok')
