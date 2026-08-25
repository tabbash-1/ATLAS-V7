from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import edge_evidence_overlap as overlap

VERSION = 'EDGE_EVIDENCE_ALIGNED_COHORT_V1'
LAYERS = ('profit_engine', 'microstructure', 'volatility')


def _timestamp_ms(row):
    try:
        value = row.get('forward_captured_at_ms')
        if value is not None:
            return int(value)
    except Exception:
        pass
    text = row.get('captured_at')
    if text:
        try:
            return int(datetime.fromisoformat(str(text).replace('Z', '+00:00')).timestamp() * 1000)
        except Exception:
            pass
    return None


def _read(path, schema):
    path = Path(path)
    rows = []
    if not path.exists():
        return rows, {'file_exists': False, 'missing_timestamp_rows': 0}
    missing_ts = 0
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get('schema') != schema:
                continue
            if row.get('production_signal_qualified') is not True or row.get('research_sample') is True:
                continue
            if not row.get('forward_id'):
                continue
            ts = _timestamp_ms(row)
            if ts is None:
                missing_ts += 1
            rows.append((str(row['forward_id']), ts))
    return rows, {'file_exists': True, 'missing_timestamp_rows': missing_ts}


def audit(data_dir):
    data_dir = Path(data_dir)
    rows = {}
    stats = {}
    for layer in LAYERS:
        rows[layer], stats[layer] = _read(data_dir / overlap.FILES[layer], overlap.SCHEMAS[layer])

    missing_files = [layer for layer in LAYERS if not stats[layer]['file_exists']]
    first_ts = {
        layer: min((ts for _, ts in rows[layer] if ts is not None), default=None)
        for layer in LAYERS
    }
    base = {
        'version': VERSION,
        'method': 'LATEST_FIRST_LAYER_TIMESTAMP_THEN_EXACT_FORWARD_ID_COVERAGE',
        'first_frozen_timestamp_ms_by_layer': first_ts,
        'outcomes_read': False,
        'historical_backfill_performed': False,
        'historical_features_recomputed': False,
        'research_only': True,
        'can_override_production': False,
        'gate_promoted': False,
    }
    if missing_files:
        return {**base, 'status': 'COLLECTING', 'aligned_cohort_complete': False, 'aligned_common_forward_ids': [], 'aligned_common_count': 0, 'blockers': ['FROZEN_EVIDENCE_SIDECAR_MISSING'], 'missing_files': missing_files}
    if any(first_ts[layer] is None for layer in LAYERS):
        return {**base, 'status': 'COLLECTING', 'aligned_cohort_complete': False, 'aligned_common_forward_ids': [], 'aligned_common_count': 0, 'blockers': ['WAITING_FOR_FIRST_FROZEN_SIGNAL_IN_ALL_LAYERS'], 'missing_files': []}
    missing_ts = {layer: stats[layer]['missing_timestamp_rows'] for layer in LAYERS if stats[layer]['missing_timestamp_rows']}
    if missing_ts:
        return {**base, 'status': 'TIMESTAMP_INTEGRITY_BLOCKED', 'aligned_cohort_complete': False, 'aligned_common_forward_ids': [], 'aligned_common_count': 0, 'blockers': ['FROZEN_FORWARD_TIMESTAMP_REQUIRED_FOR_ALIGNMENT'], 'missing_timestamp_rows_by_layer': missing_ts, 'missing_files': []}

    start = max(first_ts.values())
    ids_list = {layer: [fid for fid, ts in rows[layer] if ts >= start] for layer in LAYERS}
    sets = {layer: set(ids_list[layer]) for layer in LAYERS}
    duplicates = {layer: len(ids_list[layer]) - len(sets[layer]) for layer in LAYERS}
    union = set().union(*(sets[layer] for layer in LAYERS))
    common = set.intersection(*(sets[layer] for layer in LAYERS))
    complete = bool(union and all(sets[layer] == union for layer in LAYERS) and not any(duplicates.values()))
    blockers = []
    if any(duplicates.values()):
        blockers.append('DUPLICATE_FORWARD_IDS_IN_ALIGNED_COHORT')
    if union and not all(sets[layer] == union for layer in LAYERS):
        blockers.append('ALIGNED_FROZEN_SIGNAL_COHORT_INCOMPLETE')
    if not union:
        blockers.append('NO_ALIGNED_FROZEN_SIGNAL_AVAILABLE')

    return {
        **base,
        'status': 'ALIGNED_COHORT_COMPLETE' if complete else 'ALIGNED_COHORT_MISMATCH' if union else 'COLLECTING',
        'aligned_start_ms': start,
        'pre_alignment_rows_excluded_by_layer': {layer: sum(1 for _, ts in rows[layer] if ts < start) for layer in LAYERS},
        'aligned_unique_forward_ids_by_layer': {layer: len(sets[layer]) for layer in LAYERS},
        'aligned_common_forward_ids': sorted(common),
        'aligned_common_count': len(common),
        'aligned_union_count': len(union),
        'aligned_missing_forward_ids_by_layer': {layer: sorted(union - sets[layer]) for layer in LAYERS},
        'aligned_duplicate_rows_by_layer': duplicates,
        'aligned_cohort_complete': complete,
        'blockers': blockers,
        'missing_files': [],
    }
