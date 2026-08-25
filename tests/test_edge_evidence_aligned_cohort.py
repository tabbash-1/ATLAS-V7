import json
from pathlib import Path

import edge_evidence_aligned_cohort as aligned
import edge_evidence_overlap as overlap


def _row(layer, fid, ts):
    return {
        'schema': overlap.SCHEMAS[layer],
        'forward_id': fid,
        'forward_captured_at_ms': ts,
        'production_signal_qualified': True,
        'research_sample': False,
    }


def _write(data_dir, layer, rows):
    path = Path(data_dir) / overlap.FILES[layer]
    path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')


def test_historical_rollout_mismatch_is_excluded_before_common_activation(tmp_path):
    _write(tmp_path, 'profit_engine', [_row('profit_engine', 'F1', 100), _row('profit_engine', 'F2', 200), _row('profit_engine', 'F3', 300), _row('profit_engine', 'F4', 400)])
    _write(tmp_path, 'microstructure', [_row('microstructure', 'F2', 200), _row('microstructure', 'F3', 300), _row('microstructure', 'F4', 400)])
    _write(tmp_path, 'volatility', [_row('volatility', 'F3', 300), _row('volatility', 'F4', 400)])
    out = aligned.audit(tmp_path)
    assert out['status'] == 'ALIGNED_COHORT_COMPLETE'
    assert out['aligned_start_ms'] == 300
    assert out['aligned_common_forward_ids'] == ['F3', 'F4']
    assert out['pre_alignment_rows_excluded_by_layer'] == {'profit_engine': 2, 'microstructure': 1, 'volatility': 0}
    assert out['historical_backfill_performed'] is False
    assert out['outcomes_read'] is False


def test_missing_capture_after_common_activation_fails_closed(tmp_path):
    _write(tmp_path, 'profit_engine', [_row('profit_engine', 'F1', 100), _row('profit_engine', 'F2', 200), _row('profit_engine', 'F3', 300)])
    _write(tmp_path, 'microstructure', [_row('microstructure', 'F2', 200), _row('microstructure', 'F3', 300)])
    _write(tmp_path, 'volatility', [_row('volatility', 'F2', 200)])
    out = aligned.audit(tmp_path)
    assert out['aligned_start_ms'] == 200
    assert out['status'] == 'ALIGNED_COHORT_MISMATCH'
    assert out['aligned_cohort_complete'] is False
    assert 'F3' in out['aligned_missing_forward_ids_by_layer']['volatility']
    assert 'ALIGNED_FROZEN_SIGNAL_COHORT_INCOMPLETE' in out['blockers']


def test_duplicate_after_activation_is_integrity_blocker(tmp_path):
    _write(tmp_path, 'profit_engine', [_row('profit_engine', 'F1', 100), _row('profit_engine', 'F1', 100)])
    _write(tmp_path, 'microstructure', [_row('microstructure', 'F1', 100)])
    _write(tmp_path, 'volatility', [_row('volatility', 'F1', 100)])
    out = aligned.audit(tmp_path)
    assert out['aligned_cohort_complete'] is False
    assert 'DUPLICATE_FORWARD_IDS_IN_ALIGNED_COHORT' in out['blockers']


def test_missing_timestamp_fails_closed_instead_of_guessing_history(tmp_path):
    bad = _row('profit_engine', 'OLD', 100)
    bad.pop('forward_captured_at_ms')
    _write(tmp_path, 'profit_engine', [bad, _row('profit_engine', 'F1', 200)])
    _write(tmp_path, 'microstructure', [_row('microstructure', 'F1', 200)])
    _write(tmp_path, 'volatility', [_row('volatility', 'F1', 200)])
    out = aligned.audit(tmp_path)
    assert out['status'] == 'TIMESTAMP_INTEGRITY_BLOCKED'
    assert 'FROZEN_FORWARD_TIMESTAMP_REQUIRED_FOR_ALIGNMENT' in out['blockers']


def test_missing_sidecars_collects_without_outcome_access(tmp_path):
    out = aligned.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['aligned_cohort_complete'] is False
    assert out['outcomes_read'] is False
