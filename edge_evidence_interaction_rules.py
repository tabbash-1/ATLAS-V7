"""ATLAS immutable preregistered cross-layer interaction rule manifest.

This module declares the exact interaction hypothesis BEFORE any interaction
outcome validator is allowed to read outcomes. It is intentionally separate from
the already-frozen protocol registration so an old protocol manifest is never
silently rewritten.

The only candidate rule is semantic and outcome-free:
- Profit regime relation must be REGIME_ALIGNED.
- Microstructure relation must be ALIGNED.
- For each preregistered volatility horizon independently, both target and stop
  must be PLAUSIBLE_VS_EMPIRICAL_P80.

No alternative rule, threshold, best-cell selection, horizon selection, weighting
or fallback is permitted after outcomes are observed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import edge_evidence_interaction_protocol as protocol

VERSION = 'EDGE_EVIDENCE_INTERACTION_RULES_V1_PREREGISTERED'
SCHEMA = 'ATLAS_INTERACTION_RULE_PREREGISTRATION_V1'
REGISTRATION_FILENAME = 'interaction_rule_preregistration.json'
RULE_ID = 'H1_THREE_LAYER_FAVORABLE_CONFLUENCE'


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def _hash(payload):
    return hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()


def build_manifest(protocol_manifest):
    p = protocol_manifest if isinstance(protocol_manifest, dict) else {}
    p_hash = p.get('protocol_hash')
    horizons = sorted({int(x) for x in (p.get('eligible_volatility_horizons_h') or [])})
    protocol_ok = bool(
        p.get('status') == 'PREREGISTERED'
        and p_hash
        and protocol.verify_manifest(p)
        and horizons
    )
    manifest = {
        'schema': SCHEMA,
        'version': VERSION,
        'status': 'PREREGISTERED' if protocol_ok else 'BLOCKED_BY_PROTOCOL',
        'parent_protocol_hash': p_hash,
        'eligible_volatility_horizons_h': horizons,
        'rule_count': 1,
        'rules': [
            {
                'rule_id': RULE_ID,
                'description': 'Three-layer favorable confluence fixed before outcomes',
                'profit_regime_relation_equals': 'REGIME_ALIGNED',
                'microstructure_relation_to_signal_equals': 'ALIGNED',
                'volatility_target_fit_equals': 'PLAUSIBLE_VS_EMPIRICAL_P80',
                'volatility_stop_fit_equals': 'PLAUSIBLE_VS_EMPIRICAL_P80',
                'apply_identically_to_every_eligible_horizon': True,
            }
        ],
        'baseline': 'SAME_CANONICAL_PRODUCTION_SETTLED_COHORT_IN_SAME_FOLD',
        'rule_selection_after_outcomes_allowed': False,
        'alternative_rule_search_allowed': False,
        'grid_search_allowed': False,
        'threshold_tuning_allowed': False,
        'best_cell_selection_allowed': False,
        'horizon_selection_allowed': False,
        'fallback_rule_allowed': False,
        'weights_allowed': False,
        'outcomes_read': False,
        'performance_metrics_computed': False,
        'gate_promoted': False,
        'can_override_production': False,
        'research_only': True,
        'blockers': [] if protocol_ok else ['PARENT_PROTOCOL_NOT_READY'],
    }
    manifest['rules_hash'] = _hash(manifest)
    return manifest


def verify_manifest(manifest, protocol_manifest=None):
    if not isinstance(manifest, dict) or not manifest.get('rules_hash'):
        return False
    payload = dict(manifest)
    expected = payload.pop('rules_hash', None)
    if expected != _hash(payload):
        return False
    if protocol_manifest is not None:
        if not isinstance(protocol_manifest, dict):
            return False
        if manifest.get('parent_protocol_hash') != protocol_manifest.get('protocol_hash'):
            return False
        if not protocol.verify_manifest(protocol_manifest):
            return False
    return True


def _registration_file(collector):
    data = getattr(collector, 'DATA', None)
    return (Path(data) / REGISTRATION_FILENAME) if data is not None else None


def _atomic_write(path, manifest):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(_canonical_json(manifest) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def _load(path, protocol_manifest):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as exc:
        return None, f'{type(exc).__name__}: {exc}'
    if not isinstance(value, dict):
        return None, 'RULE_REGISTRATION_NOT_JSON_OBJECT'
    if value.get('status') != 'PREREGISTERED':
        return value, 'RULE_REGISTRATION_STATUS_NOT_PREREGISTERED'
    if not verify_manifest(value, protocol_manifest):
        return value, 'RULE_REGISTRATION_HASH_OR_PARENT_INVALID'
    return value, None


def install(collector):
    """Freeze rules once, read-only, without wrapping Production or Forward."""
    if getattr(collector, '_EDGE_EVIDENCE_INTERACTION_RULES_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_INTERACTION_RULES_STATE', {})

    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    protocol_state = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE', None)
    protocol_manifest = protocol_state.get('manifest') if isinstance(protocol_state, dict) else None
    path = _registration_file(collector)
    locked = False
    persistence_error = None

    if path is not None and path.exists():
        manifest, persistence_error = _load(path, protocol_manifest)
        locked = True
        if manifest is None:
            manifest = {
                'status': 'REGISTRATION_CORRUPT',
                'rules_hash': None,
                'parent_protocol_hash': (protocol_manifest or {}).get('protocol_hash'),
                'rules': [],
                'blockers': ['PERSISTED_RULE_PREREGISTRATION_UNREADABLE'],
            }
    else:
        manifest = build_manifest(protocol_manifest)
        if manifest.get('status') == 'PREREGISTERED':
            if path is not None:
                try:
                    _atomic_write(path, manifest)
                except Exception as exc:
                    persistence_error = f'{type(exc).__name__}: {exc}'
                else:
                    locked = True
            else:
                locked = True

    state = {
        'enabled': True,
        'version': VERSION,
        'read_only': True,
        'registration_file': str(path) if path is not None else None,
        'registration_locked': locked,
        'persistence_error': persistence_error,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'manifest': manifest,
    }

    def refresh():
        # A present/locked registration is never silently replaced.
        if state['registration_locked']:
            if path is not None:
                pstate = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE', None)
                pmanifest = pstate.get('manifest') if isinstance(pstate, dict) else None
                loaded, err = _load(path, pmanifest)
                state['persistence_error'] = err
                if loaded is not None:
                    state['manifest'] = loaded
                else:
                    state['manifest'] = {
                        'status': 'REGISTRATION_CORRUPT',
                        'rules_hash': None,
                        'parent_protocol_hash': (pmanifest or {}).get('protocol_hash'),
                        'rules': [],
                        'blockers': ['PERSISTED_RULE_PREREGISTRATION_UNREADABLE'],
                    }
            return state['manifest']

        pstate = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE', None)
        pmanifest = pstate.get('manifest') if isinstance(pstate, dict) else None
        candidate = build_manifest(pmanifest)
        state['manifest'] = candidate
        if candidate.get('status') == 'PREREGISTERED':
            if path is not None:
                try:
                    _atomic_write(path, candidate)
                except Exception as exc:
                    state['persistence_error'] = f'{type(exc).__name__}: {exc}'
                    return state['manifest']
            state['registration_locked'] = True
            state['persistence_error'] = None
        return state['manifest']

    collector.EDGE_EVIDENCE_INTERACTION_RULES_STATE = state
    collector.edge_evidence_interaction_rules_refresh = refresh
    collector._EDGE_EVIDENCE_INTERACTION_RULES_INSTALLED = True

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('interaction rules mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('interaction rules mutated forward_observe')
    return state
