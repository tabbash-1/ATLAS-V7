import research_memory_bridge as bridge


class FakeCollector:
    def __init__(self):
        self.forward_calls = []
        self.memory_calls = []

    def forward_observe(self, row):
        self.forward_calls.append(row)
        return {'stored': True, 'record': row}

    def confluence_observe(self, payload):
        self.memory_calls.append(payload)
        return {'stored': True, 'record': payload}


def sample_row(**extra):
    row = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100.0,
        'final_score': 56.0,
        'execution_decision': 'RESEARCH_OBSERVATION_ONLY',
        'research_sampling_lane': True,
        'auto_source': 'CLOUD_FORWARD_SHADOW_DIRECTION_RESEARCH',
        'playbook_primary': 'SHADOW_DIRECTIONAL_PROXY',
        'relative_volume': 1.1,
        'volume_quality': 48,
    }
    row.update(extra)
    return row


def test_build_payload_maps_direction_and_price():
    payload = bridge.build_confluence_payload(sample_row())
    assert payload['symbol'] == 'BTCUSDT'
    assert payload['price'] == 100.0
    assert payload['signal'] == 'BUY'
    assert payload['base_signal'] == 'BUY'
    assert payload['gate_state'] == 'RESEARCH'
    assert payload['cloud_memory_bridge'] is True


def test_install_mirrors_new_cloud_rows_only():
    c = FakeCollector()
    state = bridge.install(c)
    result = c.forward_observe(sample_row())
    assert result['stored'] is True
    assert len(c.memory_calls) == 1
    assert c.memory_calls[0]['signal'] == 'BUY'
    assert state['mirrored'] == 1

    c.forward_observe({
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 101,
        'auto_source': 'MANUAL_TEST', 'final_score': 80,
    })
    assert len(c.memory_calls) == 1
    assert state['skipped_non_cloud'] == 1


def test_bridge_is_fail_open_when_memory_write_fails():
    c = FakeCollector()
    def broken(_payload):
        raise RuntimeError('memory unavailable')
    c.confluence_observe = broken
    state = bridge.install(c)
    result = c.forward_observe(sample_row(direction='SHORT'))
    assert result['stored'] is True
    assert state['mirror_errors'] == 1
    assert 'memory unavailable' in state['last_error']


def test_deduped_forward_row_is_not_mirrored():
    class DedupCollector(FakeCollector):
        def forward_observe(self, row):
            self.forward_calls.append(row)
            return {'stored': False, 'reason': 'DEDUPED'}

    c = DedupCollector()
    state = bridge.install(c)
    result = c.forward_observe(sample_row())
    assert result['stored'] is False
    assert len(c.memory_calls) == 0
    assert state['skipped_deduped'] == 1


if __name__ == '__main__':
    test_build_payload_maps_direction_and_price()
    test_install_mirrors_new_cloud_rows_only()
    test_bridge_is_fail_open_when_memory_write_fails()
    test_deduped_forward_row_is_not_mirrored()
    print('research memory bridge tests: ok')
