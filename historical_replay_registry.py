"""Immutable registry for ATLAS historical replay features.

The registry freezes a retrospective, prior-only feature dataset BEFORE any
outcome evaluator is allowed to consume it. Once frozen it is never regenerated
or expanded automatically; corruption/hash mismatch fails closed.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import historical_microstructure_replay

VERSION = 'ATLAS_HISTORICAL_REPLAY_REGISTRY_V1_IMMUTABLE_FEATURES_BEFORE_OUTCOMES'
MIN_READY_ROWS = 60
FILE_NAME = 'historical_microstructure_replay_frozen_v1.json'

STATE = {
    'enabled': True,
    'background_only': True,
    'research_only': True,
    'live_execution': False,
    'status': 'STARTING',
    'registration_locked': False,
    'frozen_feature_rows': 0,
    'feature_dataset_sha256': None,
    'last_error': None,
    'last_checked_at': None,
    'path': None,
    'manifest': None,
}


def _now_iso(collector):
    return collector.now_iso() if hasattr(collector, 'now_iso') else dt.datetime.now(dt.timezone.utc).isoformat()


def _canonical_hash(rows):
    raw = json.dumps(rows, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _atomic_write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


def validate_manifest(obj):
    if not isinstance(obj, dict):
        return False, 'INVALID_MANIFEST'
    if obj.get('schema') != VERSION:
        return False, 'SCHEMA_MISMATCH'
    if obj.get('research_only') is not True or obj.get('live_execution') is not False:
        return False, 'SAFETY_CONTRACT_MISMATCH'
    if obj.get('outcomes_read_before_freeze') is not False:
        return False, 'OUTCOME_ACCESS_CONTRACT_MISMATCH'
    rows = obj.get('rows')
    if not isinstance(rows, list):
        return False, 'ROWS_MISSING'
    expected = str(obj.get('feature_dataset_sha256') or '')
    actual = _canonical_hash(rows)
    if not expected or expected != actual:
        return False, 'FEATURE_HASH_MISMATCH'
    if len(rows) < MIN_READY_ROWS:
        return False, 'FROZEN_SAMPLE_BELOW_MINIMUM'
    if any(x.get('outcome_known_to_builder') is not False for x in rows if isinstance(x, dict)):
        return False, 'OUTCOME_FLAG_VIOLATION'
    if any(x.get('forward_proof_equivalent') is not False for x in rows if isinstance(x, dict)):
        return False, 'FORWARD_PROOF_MISLABEL'
    return True, None


def build_candidate(collector):
    report = historical_microstructure_replay.report(collector.read_forward(), collector.read_all())
    ready_rows = [
        copy.deepcopy(x) for x in report.get('rows', [])
        if int(x.get('ready_windows') or 0) >= 2
    ]
    rows_hash = _canonical_hash(ready_rows)
    return {
        'schema': VERSION,
        'frozen_at': _now_iso(collector),
        'research_only': True,
        'live_execution': False,
        'retrospective_reconstruction': True,
        'forward_proof_equivalent': False,
        'outcomes_read_before_freeze': False,
        'settlement_files_read_before_freeze': False,
        'future_data_allowed': False,
        'minimum_ready_rows': MIN_READY_ROWS,
        'feature_rows': len(ready_rows),
        'source_feature_report_schema': report.get('schema'),
        'source_total_feature_rows': report.get('feature_rows'),
        'source_first_forward_ms': report.get('first_forward_ms'),
        'source_last_forward_ms': report.get('last_forward_ms'),
        'feature_dataset_sha256': rows_hash,
        'rows': ready_rows,
    }


def refresh(collector, path: Path):
    STATE['last_checked_at'] = _now_iso(collector)
    STATE['path'] = str(path)
    try:
        if path.exists():
            obj = json.loads(path.read_text(encoding='utf-8'))
            ok, err = validate_manifest(obj)
            if not ok:
                STATE.update({
                    'status': 'REGISTRATION_CORRUPT',
                    'registration_locked': True,
                    'last_error': err,
                    'manifest': None,
                    'frozen_feature_rows': 0,
                    'feature_dataset_sha256': None,
                })
                return copy.deepcopy(STATE)
            STATE.update({
                'status': 'FROZEN_READY',
                'registration_locked': True,
                'last_error': None,
                'manifest': obj,
                'frozen_feature_rows': len(obj.get('rows') or []),
                'feature_dataset_sha256': obj.get('feature_dataset_sha256'),
            })
            return copy.deepcopy(STATE)

        candidate = build_candidate(collector)
        n = int(candidate.get('feature_rows') or 0)
        if n < MIN_READY_ROWS:
            STATE.update({
                'status': 'COLLECTING_FEATURES',
                'registration_locked': False,
                'last_error': None,
                'manifest': None,
                'frozen_feature_rows': n,
                'feature_dataset_sha256': candidate.get('feature_dataset_sha256'),
            })
            return copy.deepcopy(STATE)

        _atomic_write(path, candidate)
        ok, err = validate_manifest(candidate)
        if not ok:
            raise RuntimeError(err or 'POST_WRITE_VALIDATION_FAILED')
        STATE.update({
            'status': 'FROZEN_READY',
            'registration_locked': True,
            'last_error': None,
            'manifest': candidate,
            'frozen_feature_rows': n,
            'feature_dataset_sha256': candidate.get('feature_dataset_sha256'),
        })
        return copy.deepcopy(STATE)
    except Exception as exc:
        STATE.update({
            'status': 'UNAVAILABLE',
            'last_error': f'{type(exc).__name__}: {exc}',
        })
        return copy.deepcopy(STATE)


def install(collector):
    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    path = data_dir / FILE_NAME
    collector.HISTORICAL_REPLAY_REGISTRY_STATE = STATE

    def loop():
        time.sleep(18)
        while True:
            refresh(collector, path)
            # Once frozen, keep validating the immutable artifact but never rebuild.
            time.sleep(900)

    threading.Thread(target=loop, daemon=True, name='atlas-historical-replay-registry').start()
    return STATE
