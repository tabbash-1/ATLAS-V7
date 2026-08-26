"""Immutable prospective cohort manifest for decision-time microstructure validation.

The cohort is registered before any eligible Forward row is accepted. Only rows
written with the new decision-time freeze schema on/after cohort_start_ms may be
used. This module never reads outcomes.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import Path

VERSION = 'ATLAS_PROSPECTIVE_MICROSTRUCTURE_COHORT_V1_12H'
FILE_NAME = 'prospective_microstructure_cohort_v1.json'
FREEZE_SCHEMA = 'ATLAS_FORWARD_MICROSTRUCTURE_FREEZE_V1_PRIOR_ONLY'

RULES = {
    'primary_horizon_hours': 12,
    'secondary_descriptive_horizon_hours': 24,
    'eligible_freeze_schema': FREEZE_SCHEMA,
    'exposed_group': ['ALIGNED'],
    'control_group': ['OPPOSED_OR_CROWDED', 'MIXED_OR_INSUFFICIENT'],
    'minimum_matured_exposed': 15,
    'minimum_matured_control': 15,
    'chronological_folds': 3,
    'primary_metrics': ['directional_mean_return_pct','directional_median_return_pct','positive_rate_pct'],
    'edge_claim_thresholds': {
        'minimum_mean_return_delta_pct_points': 0.10,
        'minimum_positive_rate_delta_percentage_points': 5.0,
        'minimum_positive_mean_delta_folds': 2,
    },
    'missing_return_policy': 'EXCLUDE_WITH_COUNTS_NEVER_ZERO_FILL',
    'selection_policy': 'NO_GRID_SEARCH_NO_BEST_HORIZON_NO_POST_OUTCOME_RULE_CHANGES',
    'promotion_policy': 'FORWARD_RESEARCH_EVIDENCE_CANNOT_OVERRIDE_PRODUCTION_OR_ENABLE_LIVE_EXECUTION',
}

STATE = {
    'status': 'STARTING',
    'registration_locked': False,
    'cohort_hash': None,
    'cohort_start_ms': None,
    'cohort_start_at': None,
    'last_error': None,
    'manifest': None,
    'outcomes_read_before_registration': False,
    'research_only': True,
    'live_execution': False,
    'can_override_production': False,
}


def _hash(obj):
    raw=json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _body(start_ms,start_at):
    return {
        'schema': VERSION,
        'cohort_start_ms': int(start_ms),
        'cohort_start_at': str(start_at),
        'eligible_freeze_schema': FREEZE_SCHEMA,
        'rules': copy.deepcopy(RULES),
        'outcomes_read_before_registration': False,
        'research_only': True,
        'live_execution': False,
        'can_override_production': False,
    }


def build_manifest(start_ms,start_at):
    body=_body(start_ms,start_at)
    return {**body,'cohort_hash':_hash(body)}


def validate_manifest(obj):
    if not isinstance(obj,dict): return False,'INVALID_MANIFEST'
    if obj.get('schema') != VERSION: return False,'SCHEMA_MISMATCH'
    if obj.get('eligible_freeze_schema') != FREEZE_SCHEMA: return False,'FREEZE_SCHEMA_MISMATCH'
    if obj.get('rules') != RULES: return False,'RULES_MISMATCH'
    if obj.get('outcomes_read_before_registration') is not False: return False,'OUTCOME_ACCESS_CONTRACT_MISMATCH'
    if obj.get('research_only') is not True or obj.get('live_execution') is not False or obj.get('can_override_production') is not False:
        return False,'SAFETY_CONTRACT_MISMATCH'
    try:
        if int(obj.get('cohort_start_ms') or 0) <= 0: return False,'START_MISSING'
    except Exception:
        return False,'START_INVALID'
    body={k:obj.get(k) for k in ('schema','cohort_start_ms','cohort_start_at','eligible_freeze_schema','rules','outcomes_read_before_registration','research_only','live_execution','can_override_production')}
    if str(obj.get('cohort_hash') or '') != _hash(body): return False,'HASH_MISMATCH'
    return True,None


def _atomic_write(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True),encoding='utf-8')
    os.replace(tmp,path)


def register(collector,path=None):
    if path is None:
        path=Path(getattr(collector,'DATA',Path('.'))) / FILE_NAME
    path=Path(path)
    try:
        if path.exists():
            obj=json.loads(path.read_text(encoding='utf-8'))
        else:
            start_ms=int(time.time()*1000)
            obj=build_manifest(start_ms,collector.now_iso())
            _atomic_write(path,obj)
        ok,err=validate_manifest(obj)
        if not ok:
            STATE.update({'status':'REGISTRATION_CORRUPT','registration_locked':True,'last_error':err,'manifest':None})
            return copy.deepcopy(STATE)
        STATE.update({
            'status':'PREREGISTERED',
            'registration_locked':True,
            'cohort_hash':obj['cohort_hash'],
            'cohort_start_ms':int(obj['cohort_start_ms']),
            'cohort_start_at':obj['cohort_start_at'],
            'last_error':None,
            'manifest':obj,
        })
    except Exception as exc:
        STATE.update({'status':'UNAVAILABLE','registration_locked':False,'last_error':f'{type(exc).__name__}: {exc}','manifest':None})
    return copy.deepcopy(STATE)


def install(collector):
    collector.PROSPECTIVE_MICROSTRUCTURE_COHORT_STATE=STATE
    return register(collector)
