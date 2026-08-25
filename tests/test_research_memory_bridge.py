import json
import tempfile
import threading
from pathlib import Path

import research_memory_bridge as bridge


class FakeCollector:
    def __init__(self):
        self.forward_calls = []
        self._tmp = tempfile.TemporaryDirectory()
        self.CONFLUENCE_ARCHIVE = Path(self._tmp.name) / 'confluence_memory.jsonl'
        self.ARCHIVE_LOCK = threading.RLock()

    def forward_observe(self, row):
        self.forward_calls.append(row)
        return {'stored': True, 'record': dict(row)}

    def read_confluence_all(self):
        out = []
        if self.CONFLUENCE_ARCHIVE.exists():
            with self.CONFLUENCE_ARCHIVE.open() as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
        return out

    def now_iso(self):
        return '2026-08-23T00:00:00+00:00'


def sample_row(**extra):
    row = {
        'schema': 'ATLAS_FORWARD_V1',
        'id': 'fwd-1',
        'captured_at': '2026-08-23T00:00:00+00:00',
        'captured_at_ms': 1_000_000,
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


def test_build_payload_maps_direction_price_and_lineage():
    payload = bridge.build_confluence_payload(sample_row())
    assert payload['symbol'] == 'BTCUSDT'
    assert payload['price'] == 100.0
    assert payload['signal'] == 'BUY'
    assert payload['base_signal'] == 'BUY'
    assert payload['gate_state'] == 'RESEARCH'
    assert payload['cloud_memory_bridge'] is True
    assert payload['forward_observation_id'] == 'fwd-1'
    assert payload['forward_captured_at_ms'] == 1_000_000
    assert payload['auto_source'].startswith('CLOUD_FORWARD')


def test_canonical_forward_result_accepts_direct_production_row():
    submitted = {
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100,
        'auto_source': 'CLOUD_FORWARD_CI_BRIDGE_TEST',
    }
    stored = sample_row(id='server-generated-id', captured_at_ms=7_777_777)
    canonical = bridge._canonical_forward_result(stored, submitted)
    assert canonical is stored
    assert canonical['id'] == 'server-generated-id'
    assert canonical['captured_at_ms'] == 7_777_777


def test_install_handles_direct_production_return_and_persists_generated_id():
    class DirectReturnCollector(FakeCollector):
        def forward_observe(self, row):
            self.forward_calls.append(row)
            stored = dict(row)
            stored.update({
                'schema': 'ATLAS_FORWARD_V1',
                'id': 'generated-by-server',
                'captured_at': '2026-08-23T01:00:00+00:00',
                'captured_at_ms': 3_600_000,
            })
            return stored

    c = DirectReturnCollector()
    state = bridge.install(c)
    result = c.forward_observe({
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100,
        'final_score': 56, 'execution_decision': 'RESEARCH_OBSERVATION_ONLY',
        'research_sampling_lane': True,
        'playbook_primary': 'SHADOW_DIRECTIONAL_PROXY',
        'auto_source': 'CLOUD_FORWARD_CI_BRIDGE_TEST',
    })
    assert result['id'] == 'generated-by-server'
    rows = c.read_confluence_all()
    assert len(rows) == 1
    assert rows[0]['forward_observation_id'] == 'generated-by-server'
    assert rows[0]['forward_captured_at_ms'] == 3_600_000
    assert state['mirrored'] == 1
    assert state['exact_lineage_mirrors'] == 1


def test_install_persists_exact_lineage_cloud_row_only():
    c = FakeCollector()
    state = bridge.install(c)
    result = c.forward_observe(sample_row())
    assert result['stored'] is True
    rows = c.read_confluence_all()
    assert len(rows) == 1
    assert rows[0]['signal'] == 'BUY'
    assert rows[0]['forward_observation_id'] == 'fwd-1'
    assert rows[0]['captured_at_ms'] == 1_000_000
    assert state['mirrored'] == 1
    assert state['exact_lineage_mirrors'] == 1

    c.forward_observe({
        'id': 'manual-1', 'captured_at_ms': 5_000_000,
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 101,
        'auto_source': 'MANUAL_TEST', 'final_score': 80,
    })
    assert len(c.read_confluence_all()) == 1
    assert state['skipped_non_cloud'] == 1


def test_bridge_is_fail_open_when_memory_write_fails():
    c = FakeCollector()
    c.CONFLUENCE_ARCHIVE = Path(c._tmp.name)
    state = bridge.install(c)
    result = c.forward_observe(sample_row(direction='SHORT'))
    assert result['stored'] is True
    assert state['mirror_errors'] == 1
    assert state['last_error']


def test_deduped_forward_row_is_not_mirrored():
    class DedupCollector(FakeCollector):
        def forward_observe(self, row):
            self.forward_calls.append(row)
            return {'stored': False, 'reason': 'DEDUPED'}

    c = DedupCollector()
    state = bridge.install(c)
    result = c.forward_observe(sample_row())
    assert result['stored'] is False
    assert len(c.read_confluence_all()) == 0
    assert state['skipped_deduped'] == 1


def test_memory_dedupe_does_not_inflate_mirrored_counter():
    c = FakeCollector()
    state = bridge.install(c)
    c.forward_observe(sample_row(id='fwd-a', captured_at_ms=1_000_000))
    c.forward_observe(sample_row(id='fwd-b', captured_at_ms=1_000_000 + 10 * 60 * 1000))
    assert len(c.read_confluence_all()) == 1
    assert state['mirrored'] == 1
    assert state['mirror_deduped'] == 1
    assert state['mirror_attempts'] == 2


def test_strict_chain_rejects_later_horizon_after_gap():
    clean, rejected = bridge._strict_chain({'1': 1.0, '4': 2.0, '12': None, '24': 4.0})
    assert clean == {'1': 1.0, '4': 2.0, '12': None, '24': None}
    assert rejected == ['24']
    assert bridge._chain_state(clean, rejected) == 'SPARSE_SAMPLING_GAP'


def test_incomplete_prefix_is_waiting_not_integrity_error():
    clean, rejected = bridge._strict_chain({'1': 1.0, '4': 2.0})
    assert rejected == []
    assert clean == {'1': 1.0, '4': 2.0, '12': None, '24': None}
    assert bridge._chain_state(clean, rejected) == 'AWAITING_LATER_MATURITY'


def test_reconcile_prefers_exact_canonical_forward_lineage():
    memory = [{
        'symbol': 'BTCUSDT', 'captured_at_ms': 1_000_000, 'price': 100.0,
        'base_signal': 'BUY', 'forward_observation_id': 'exact-1',
        'forward_return_pct': {'1': 9.0, '4': 9.0, '12': None, '24': 9.0},
    }]
    forward = [sample_row(
        id='exact-1', captured_at_ms=9_000_000,
        forward_return_pct={'1': 0.5, '4': 1.0, '12': 1.5, '24': 2.0},
    )]
    rows, metrics = bridge.reconcile_confluence_rows(memory, forward)
    assert rows[0]['forward_evidence_source'] == 'CANONICAL_FORWARD_ARCHIVE'
    assert rows[0]['forward_link_method'] == 'EXACT_ID'
    assert rows[0]['forward_return_pct'] == {'1': 0.5, '4': 1.0, '12': 1.5, '24': 2.0}
    assert rows[0]['maturity_integrity']['state'] == 'COMPLETE_24H'
    assert metrics['linked_to_forward'] == 1
    assert metrics['exact_lineage_links'] == 1
    assert metrics['complete_24h_rows'] == 1
    assert metrics['gap_rows'] == 0
    assert metrics['hard_integrity_errors'] == 0


def test_legacy_fuzzy_match_requires_same_direction():
    memory = [{
        'symbol': 'BTCUSDT', 'captured_at_ms': 1_000_000, 'price': 100.0,
        'base_signal': 'BUY', 'forward_return_pct': {},
    }]
    wrong = sample_row(id='short-1', direction='SHORT', captured_at_ms=1_000_100,
                       forward_return_pct={'1': 1, '4': 1, '12': 1, '24': 1})
    rows, metrics = bridge.reconcile_confluence_rows(memory, [wrong])
    assert rows[0]['forward_evidence_source'] == 'CONFLUENCE_FALLBACK'
    assert metrics['linked_to_forward'] == 0
    assert metrics['unlinked_rows'] == 1


def test_exact_id_lineage_conflict_is_hard_error_and_never_fuzzy_matches():
    memory = [{
        'symbol': 'BTCUSDT', 'captured_at_ms': 1_000_000, 'price': 100.0,
        'base_signal': 'BUY', 'forward_observation_id': 'exact-1',
        'forward_return_pct': {'1': 0.1},
    }]
    conflicting = sample_row(
        id='exact-1', symbol='ETHUSDT', direction='LONG', captured_at_ms=1_000_010,
        forward_return_pct={'1': 1, '4': 1, '12': 1, '24': 1},
    )
    fuzzy_candidate = sample_row(
        id='other', symbol='BTCUSDT', direction='LONG', captured_at_ms=1_000_020,
        forward_return_pct={'1': 2, '4': 2, '12': 2, '24': 2},
    )
    rows, metrics = bridge.reconcile_confluence_rows(memory, [conflicting, fuzzy_candidate])
    assert rows[0]['forward_evidence_source'] == 'LINEAGE_CONFLICT'
    assert rows[0]['forward_link_method'] is None
    assert rows[0]['maturity_integrity']['hard_integrity_error'] is True
    assert metrics['lineage_conflicts'] == 1
    assert metrics['hard_integrity_errors'] == 1
    assert metrics['linked_to_forward'] == 0


def test_reconcile_sparse_sampling_never_allows_24h_without_12h():
    memory = [{
        'symbol': 'BTCUSDT', 'captured_at_ms': 1_000_000, 'price': 100.0,
        'forward_return_pct': {'1': 0.5, '4': 1.0, '12': None, '24': 2.0},
    }]
    rows, metrics = bridge.reconcile_confluence_rows(memory, [])
    assert rows[0]['forward_return_pct']['24'] is None
    assert rows[0]['maturity_integrity']['rejected_horizons'] == ['24']
    assert rows[0]['maturity_integrity']['state'] == 'SPARSE_SAMPLING_GAP'
    assert rows[0]['maturity_integrity']['suppressed_for_safety'] is True
    assert metrics['sparse_sampling_rows'] == 1
    assert metrics['suppressed_later_horizons'] == 1
    assert metrics['gap_rows'] == 1
    assert metrics['rejected_horizons'] == 1
    assert metrics['hard_integrity_errors'] == 0


if __name__ == '__main__':
    test_build_payload_maps_direction_price_and_lineage()
    test_canonical_forward_result_accepts_direct_production_row()
    test_install_handles_direct_production_return_and_persists_generated_id()
    test_install_persists_exact_lineage_cloud_row_only()
    test_bridge_is_fail_open_when_memory_write_fails()
    test_deduped_forward_row_is_not_mirrored()
    test_memory_dedupe_does_not_inflate_mirrored_counter()
    test_strict_chain_rejects_later_horizon_after_gap()
    test_incomplete_prefix_is_waiting_not_integrity_error()
    test_reconcile_prefers_exact_canonical_forward_lineage()
    test_legacy_fuzzy_match_requires_same_direction()
    test_exact_id_lineage_conflict_is_hard_error_and_never_fuzzy_matches()
    test_reconcile_sparse_sampling_never_allows_24h_without_12h()
    print('research memory bridge tests: ok')
