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


if __name__ == '__main__':
    test_policy_cancel_only_cancels_active_signal()
    print('quick reentry guard policy cancel tests: ok')
