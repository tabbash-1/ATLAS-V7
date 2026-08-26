"""Immutable preregistration for ATLAS historical replay evaluation.

This file declares the retrospective evaluation hypothesis BEFORE the frozen
historical feature dataset is allowed to be joined to any forward returns.
The protocol is tied to the immutable feature-dataset SHA256 and persists once.
It contains no outcome reader and cannot promote Production behavior.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

VERSION = 'ATLAS_HISTORICAL_EVALUATION_PROTOCOL_V1_12H_PREREGISTERED'
FILE_NAME = 'historical_evaluation_protocol_v1.json'

# 12h is selected ex ante from the already-published base historical replay,
# where it had >=100 matured cases and positive mean directional return. It is
# NOT selected from microstructure subgroup outcomes (which remain unread here).
PROTOCOL_RULES = {
    'primary_horizon_hours': 12,
    'secondary_descriptive_horizon_hours': 24,
    'primary_feature': 'relation_to_signal',
    'primary_exposed_group': ['ALIGNED'],
    'primary_control_group': ['OPPOSED_OR_CROWDED', 'MIXED_OR_INSUFFICIENT'],
    'minimum_total_frozen_rows': 60,
    'minimum_matured_rows_per_primary_group': 15,
    'chronological_folds': 3,
    'primary_metrics': [
        'directional_mean_return_pct',
        'directional_median_return_pct',
        'positive_rate_pct',
    ],
    'edge_claim_thresholds': {
        'minimum_mean_return_delta_pct_points': 0.10,
        'minimum_positive_rate_delta_percentage_points': 5.0,
        'minimum_positive_mean_delta_folds': 2,
    },
    'missing_or_unmatured_policy': 'EXCLUDE_WITH_COUNTS; NEVER_IMPUTE',
    'open_or_missing_return_policy': 'EXCLUDE_WITH_COUNTS; NEVER_ZERO_FILL',
    'selection_policy': 'NO_GRID_SEARCH_NO_BEST_HORIZON_NO_POST_OUTCOME_RULE_CHANGES',
    'promotion_policy': 'RETROSPECTIVE_EVIDENCE_CANNOT_PROMOTE_PRODUCTION_OR_LIVE_EXECUTION',
}

STATE = {
    'status': 'STARTING',
    'registration_locked': False,
    'protocol_hash': None,
    'feature_dataset_sha256': None,
    'last_error': None,
    'manifest': None,
}


def _canonical_hash(obj):
    raw = json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _body(feature_hash):
    return {
        'schema': VERSION,
        'research_only': True,
        'live_execution': False,
        'outcomes_read_before_registration': False,
        'can_override_production': False,
        'feature_dataset_sha256': str(feature_hash or ''),
        'rules': copy.deepcopy(PROTOCOL_RULES),
    }


def build_manifest(feature_hash, registered_at):
    body = _body(feature_hash)
    return {
        **body,
        'registered_at': registered_at,
        'protocol_hash': _canonical_hash(body),
    }


def validate_manifest(obj, expected_feature_hash=None):
    if not isinstance(obj, dict):
        return False, 'INVALID_MANIFEST'
    if obj.get('schema') != VERSION:
        return False, 'SCHEMA_MISMATCH'
    if obj.get('research_only') is not True or obj.get('live_execution') is not False or obj.get('can_override_production') is not False:
        return False, 'SAFETY_CONTRACT_MISMATCH'
    if obj.get('outcomes_read_before_registration') is not False:
        return False, 'OUTCOME_ACCESS_CONTRACT_MISMATCH'
    feature_hash = str(obj.get('feature_dataset_sha256') or '')
    if not feature_hash:
        return False, 'FEATURE_HASH_MISSING'
    if expected_feature_hash and feature_hash != str(expected_feature_hash):
        return False, 'FEATURE_HASH_MISMATCH'
    body = {k: obj.get(k) for k in ('schema','research_only','live_execution','outcomes_read_before_registration','can_override_production','feature_dataset_sha256','rules')}
    if str(obj.get('protocol_hash') or '') != _canonical_hash(body):
        return False, 'PROTOCOL_HASH_MISMATCH'
    if obj.get('rules') != PROTOCOL_RULES:
        return False, 'RULES_MISMATCH'
    return True, None


def _atomic_write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)


def refresh(collector, path=None):
    registry = getattr(collector, 'HISTORICAL_REPLAY_REGISTRY_STATE', {}) or {}
    if path is None:
        path = Path(getattr(collector, 'DATA', Path('.'))) / FILE_NAME
    path = Path(path)

    if registry.get('status') != 'FROZEN_READY' or not registry.get('registration_locked'):
        STATE.update({'status':'BLOCKED_FEATURE_DATASET_NOT_FROZEN','registration_locked':False,'last_error':None,'manifest':None})
        return copy.deepcopy(STATE)

    feature_hash = str(registry.get('feature_dataset_sha256') or '')
    STATE['feature_dataset_sha256'] = feature_hash
    if not feature_hash:
        STATE.update({'status':'BLOCKED_FEATURE_HASH_MISSING','registration_locked':False,'last_error':'FEATURE_HASH_MISSING'})
        return copy.deepcopy(STATE)

    try:
        if path.exists():
            obj = json.loads(path.read_text(encoding='utf-8'))
            ok, err = validate_manifest(obj, feature_hash)
            if not ok:
                STATE.update({'status':'REGISTRATION_CORRUPT','registration_locked':True,'protocol_hash':None,'last_error':err,'manifest':None})
                return copy.deepcopy(STATE)
            STATE.update({'status':'PREREGISTERED','registration_locked':True,'protocol_hash':obj.get('protocol_hash'),'last_error':None,'manifest':obj})
            return copy.deepcopy(STATE)

        manifest = build_manifest(feature_hash, collector.now_iso())
        _atomic_write(path, manifest)
        ok, err = validate_manifest(manifest, feature_hash)
        if not ok:
            raise RuntimeError(err or 'POST_WRITE_VALIDATION_FAILED')
        STATE.update({'status':'PREREGISTERED','registration_locked':True,'protocol_hash':manifest.get('protocol_hash'),'last_error':None,'manifest':manifest})
    except Exception as exc:
        STATE.update({'status':'UNAVAILABLE','registration_locked':False,'protocol_hash':None,'last_error':f'{type(exc).__name__}: {exc}','manifest':None})
    return copy.deepcopy(STATE)


def install(collector):
    collector.HISTORICAL_EVALUATION_PROTOCOL_STATE = STATE
    return refresh(collector)
