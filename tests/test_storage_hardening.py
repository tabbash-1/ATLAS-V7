import threading
import storage_hardening


class FakeCollector:
    def __init__(self):
        self.ARCHIVE_LOCK = threading.RLock()
        self.calls = []

    def _forward_write(self, row):
        self.calls.append(('forward', row))
        return 'forward-ok'

    def confluence_observe(self, payload):
        self.calls.append(('confluence', payload))
        return {'stored': True}

    def event_observe(self, payload):
        self.calls.append(('event', payload))
        return {'stored': True}


def test_install_wraps_all_persistent_writers_once():
    c = FakeCollector()
    state = storage_hardening.install(c)
    assert state['enabled'] is True
    assert state['forward_write_locked'] is True
    assert state['confluence_write_locked'] is True
    assert state['event_write_locked'] is True
    assert c._forward_write({'x': 1}) == 'forward-ok'
    assert c.confluence_observe({'x': 2})['stored'] is True
    assert c.event_observe({'x': 3})['stored'] is True
    assert [x[0] for x in c.calls] == ['forward', 'confluence', 'event']

    before_forward = c._forward_write
    state2 = storage_hardening.install(c)
    assert state2 is state
    assert c._forward_write is before_forward


if __name__ == '__main__':
    test_install_wraps_all_persistent_writers_once()
    print('storage hardening tests: ok')
