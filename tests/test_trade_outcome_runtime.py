import json
import tempfile
import threading
from pathlib import Path

import trade_outcome_runtime as runtime


class FakeCollector:
    def __init__(self, root, rows):
        self.rows = rows
        self.FORWARD_ARCHIVE = Path(root) / 'champion_challenger_forward.jsonl'
        self.ARCHIVE_LOCK = threading.RLock()
        self.calls = 0
        self._persist()

    def _persist(self):
        with self.FORWARD_ARCHIVE.open('w') as handle:
            for row in self.rows:
                handle.write(json.dumps(row, separators=(',', ':')) + '\n')

    def read_forward(self):
        return self.rows

    def update_forward_returns(self):
        self.calls += 1
        updated = 0
        for row in self.rows:
            fr = row.setdefault('forward_return_pct', {})
            for key, value in (('4', 0.5), ('8', 1.25), ('12', 2.5)):
                if key not in fr:
                    fr[key] = value
                    updated += 1
        self._persist()
        return {'updated': updated, 'rows': len(self.rows)}


def test_null_official_horizon_placeholder_is_repaired_then_matured():
    with tempfile.TemporaryDirectory() as root:
        collector = FakeCollector(root, [{
            'id': 'old-signal',
            'forward_return_pct': {'1': None, '4': 0.5, '8': None, '12': 1.0, '24': None},
        }])
        result = runtime._settle_forward_maturity(collector)
        assert result['repaired_null_slots'] == 1
        assert collector.rows[0]['forward_return_pct']['8'] == 1.25
        # Legacy nulls are intentionally untouched by the official settlement repair.
        assert collector.rows[0]['forward_return_pct']['1'] is None
        assert collector.rows[0]['forward_return_pct']['24'] is None
        assert collector.calls == 1


def test_real_matured_return_is_never_rewritten():
    with tempfile.TemporaryDirectory() as root:
        collector = FakeCollector(root, [{'id': 'closed-signal', 'forward_return_pct': {'8': -1.75}}])
        runtime._settle_forward_maturity(collector)
        assert collector.rows[0]['forward_return_pct']['8'] == -1.75


def test_non_dict_forward_return_container_is_repaired_safely():
    with tempfile.TemporaryDirectory() as root:
        collector = FakeCollector(root, [{'id': 'legacy-signal', 'forward_return_pct': None}])
        result = runtime._settle_forward_maturity(collector)
        assert result['repaired_null_slots'] == 1
        assert set(collector.rows[0]['forward_return_pct']) == {'4', '8', '12'}


def test_official_horizon_contract_is_4_8_12_with_default_12():
    assert runtime.OFFICIAL_HORIZONS == (4, 8, 12)
    assert runtime.DEFAULT_HORIZON == 12


def test_public_status_never_mixes_current_start_with_previous_finish():
    state = {
        'settlement_running': True,
        'current_settlement_started_at': '2026-09-08T07:05:10+00:00',
        'last_settlement_started_at': '2026-09-08T07:05:10+00:00',
        'last_settlement_finished_at': '2026-09-08T06:58:47+00:00',
        'last_completed_settlement': {
            'started_at': '2026-09-08T06:43:47+00:00',
            'finished_at': '2026-09-08T06:58:47+00:00',
            'error': None,
        },
    }
    payload = runtime._settlement_status_payload(state)
    assert payload['settlement_running'] is True
    assert payload['current_settlement_started_at'] == '2026-09-08T07:05:10+00:00'
    assert payload['last_settlement_started_at'] == '2026-09-08T06:43:47+00:00'
    assert payload['last_settlement_finished_at'] == '2026-09-08T06:58:47+00:00'


if __name__ == '__main__':
    test_null_official_horizon_placeholder_is_repaired_then_matured()
    test_real_matured_return_is_never_rewritten()
    test_non_dict_forward_return_container_is_repaired_safely()
    test_official_horizon_contract_is_4_8_12_with_default_12()
    test_public_status_never_mixes_current_start_with_previous_finish()
    print('trade outcome runtime tests: ok')
