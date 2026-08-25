import tempfile
from pathlib import Path

from quick_reentry_guard import QuickReentryGuard


def test_active_signal_is_not_reissued():
    with tempfile.TemporaryDirectory() as root:
        g = QuickReentryGuard(Path(root) / 'guard.json', active_ttl_seconds=100, post_stop_cooldown_seconds=200)
        g.register('ETHUSDT', 'LONG', 100, 98, 104, now=1000)
        out = g.inspect('ETHUSDT', 'LONG', 101, now=1010)
        assert out['allow_new'] is False
        assert out['state'] == 'ACTIVE'
        assert out['reason'] == 'ACTIVE_SAME_DIRECTION_SIGNAL_NOT_REISSUED'


def test_stop_breach_starts_cooldown_and_persists():
    with tempfile.TemporaryDirectory() as root:
        path = Path(root) / 'guard.json'
        g = QuickReentryGuard(path, active_ttl_seconds=100, post_stop_cooldown_seconds=200)
        g.register('ETHUSDT', 'LONG', 100, 98, 104, now=1000)
        stopped = g.inspect('ETHUSDT', 'LONG', 97.9, now=1020)
        assert stopped['state'] == 'POST_STOP_COOLDOWN'
        assert stopped['reason'] == 'STOP_BREACH_DETECTED'
        g2 = QuickReentryGuard(path, active_ttl_seconds=100, post_stop_cooldown_seconds=200)
        blocked = g2.inspect('ETHUSDT', 'LONG', 99, now=1100)
        assert blocked['allow_new'] is False
        assert blocked['reason'] == 'POST_STOP_REENTRY_COOLDOWN'


def test_reentry_allowed_after_cooldown():
    with tempfile.TemporaryDirectory() as root:
        g = QuickReentryGuard(Path(root) / 'guard.json', active_ttl_seconds=100, post_stop_cooldown_seconds=200)
        g.register('ZECUSDT', 'SHORT', 100, 102, 96, now=1000)
        g.inspect('ZECUSDT', 'SHORT', 102.1, now=1020)
        out = g.inspect('ZECUSDT', 'SHORT', 101, now=1221)
        assert out['allow_new'] is True
        assert out['state'] == 'COOLDOWN_COMPLETE'


if __name__ == '__main__':
    test_active_signal_is_not_reissued()
    test_stop_breach_starts_cooldown_and_persists()
    test_reentry_allowed_after_cooldown()
    print('quick reentry guard tests: ok')
