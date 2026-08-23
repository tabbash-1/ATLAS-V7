import threading
import storage_hardening


class FakeCollector:
    def __init__(self):
        self.ARCHIVE_LOCK = threading.RLock()
        self.calls = []

    def _forward_write(self, row):
        self.calls.append(('forward', row))
        return 'forward-ok'

    def update_forward_returns(self):
        self.calls.append(('forward_update', None))
        return {'updated': 1, 'rows': 1}

    def confluence_observe(self, payload):
        self.calls.append(('confluence', payload))
        return {'stored': True}

    def event_observe(self, payload):
        self.calls.append(('event', payload))
        return {'stored': True}


def test_install_wraps_all_persistent_writers_and_rewrite_transaction_once():
    c = FakeCollector()
    state = storage_hardening.install(c)
    assert state['enabled'] is True
    assert state['forward_write_locked'] is True
    assert state['forward_update_locked'] is True
    assert state['confluence_write_locked'] is True
    assert state['event_write_locked'] is True
    assert c._forward_write({'x': 1}) == 'forward-ok'
    assert c.update_forward_returns()['updated'] == 1
    assert c.confluence_observe({'x': 2})['stored'] is True
    assert c.event_observe({'x': 3})['stored'] is True
    assert [x[0] for x in c.calls] == ['forward', 'forward_update', 'confluence', 'event']

    before_forward = c._forward_write
    before_update = c.update_forward_returns
    state2 = storage_hardening.install(c)
    assert state2 is state
    assert c._forward_write is before_forward
    assert c.update_forward_returns is before_update


if __name__ == '__main__':
    test_install_wraps_all_persistent_writers_and_rewrite_transaction_once()
    print('storage hardening tests: ok')
