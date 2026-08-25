"""ATLAS outcome-free preflight for preregistered interaction validation.

This gate uses only frozen-at-signal Profit/Microstructure/Volatility sidecars.
It answers whether reading canonical trade outcomes is even mathematically useful
yet. If the frozen common cohort or preregistered H1 candidate cohort is below
protocol minima, outcome access remains forbidden.

No settlement, R, win/loss, price path or future data is read here.
"""

from __future__ import annotations

import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules

VERSION = 'EDGE_EVIDENCE_INTERACTION_PREFLIGHT_V1_OUTCOME_FREE'


def _fid(row):
    return str((row or {}).get('forward_id') or '').strip() or None


def _eligible(row):
    return bool(
        isinstance(row, dict)
        and row.get('production_signal_qualified') is True
        and row.get('research_sample') is not True
        and _fid(row)
    )


def _index(rows):
    unique = {}
    duplicates = set()
    for row in rows or []:
        if not _eligible(row):
            continue
        fid = _fid(row)
        if fid in unique:
            duplicates.add(fid)
        else:
            unique[fid] = row
    for fid in duplicates:
        unique.pop(fid, None)
    return unique, sorted(duplicates)


def _profit_relation(row):
    pe = (row or {}).get('profit_engine')
    gate = pe.get('regime_gate') if isinstance(pe, dict) else None
    return gate.get('reason') if isinstance(gate, dict) else None


def _micro_relation(row):
    return (row or {}).get('relation_to_signal')


def _vol_fit(row, horizon):
    fits = (row or {}).get('geometry_fit_by_horizon')
    if not isinstance(fits, dict):
        return None, None
    cell = fits.get(str(horizon))
    if cell is None:
        cell = fits.get(horizon)
    if not isinstance(cell, dict):
        return None, None
    return cell.get('target_fit'), cell.get('stop_fit')


def _authorization_blockers(protocol_manifest, guard_report, rules_manifest):
    p = protocol_manifest if isinstance(protocol_manifest, dict) else {}
    g = guard_report if isinstance(guard_report, dict) else {}
    r = rules_manifest if isinstance(rules_manifest, dict) else {}
    blockers = []
    p_hash = p.get('protocol_hash')

    if not protocol.verify_manifest(p):
        blockers.append('PROTOCOL_HASH_INVALID')
    if p.get('status') != 'PREREGISTERED':
        blockers.append('PROTOCOL_NOT_PREREGISTERED')
    if g.get('status') != 'VALIDATOR_ARMED':
        blockers.append('VALIDATOR_GUARD_NOT_ARMED')
    if g.get('armed_protocol_hash') != p_hash:
        blockers.append('GUARD_PROTOCOL_HASH_MISMATCH')
    if r.get('status') != 'PREREGISTERED':
        blockers.append('RULES_NOT_PREREGISTERED')
    if not rules.verify_manifest(r, p):
        blockers.append('RULES_HASH_OR_PARENT_INVALID')
    if r.get('rule_count') != 1 or len(r.get('rules') or []) != 1:
        blockers.append('EXACTLY_ONE_PREREGISTERED_RULE_REQUIRED')
    if sorted(r.get('eligible_volatility_horizons_h') or []) != sorted(p.get('eligible_volatility_horizons_h') or []):
        blockers.append('RULE_AND_PROTOCOL_HORIZONS_DIFFER')
    return sorted(set(blockers))


def evaluate(protocol_manifest, guard_report, rules_manifest, profit_rows, micro_rows, volatility_rows):
    """Return whether canonical outcome access is allowed. Never reads outcomes."""
    auth_blockers = _authorization_blockers(protocol_manifest, guard_report, rules_manifest)
    if auth_blockers:
        return {
            'version': VERSION,
            'status': 'BLOCKED',
            'outcome_access_allowed': False,
            'outcomes_read': False,
            'performance_metrics_computed': False,
            'matched_frozen_total': 0,
            'candidate_frozen_by_horizon': {},
            'duplicate_frozen_feature_ids': [],
            'research_only': True,
            'can_override_production': False,
            'gate_promoted': False,
            'blockers': auth_blockers,
        }

    pmap, pdup = _index(profit_rows)
    mmap, mdup = _index(micro_rows)
    vmap, vdup = _index(volatility_rows)
    duplicate_ids = sorted(set(pdup) | set(mdup) | set(vdup))
    common_ids = sorted(set(pmap) & set(mmap) & set(vmap))

    p = protocol_manifest
    r = rules_manifest
    mins = p.get('minimum_samples') or {}
    min_total = int(mins.get('total_settled') or 0)
    min_cell_total = int(mins.get('total_settled_per_cell') or 0)
    horizons = sorted(int(x) for x in p.get('eligible_volatility_horizons_h') or [])
    prereg_rule = (r.get('rules') or [])[0]

    candidate_counts = {}
    for horizon in horizons:
        count = 0
        for fid in common_ids:
            target_fit, stop_fit = _vol_fit(vmap[fid], horizon)
            if (
                _profit_relation(pmap[fid]) == prereg_rule.get('profit_regime_relation_equals')
                and _micro_relation(mmap[fid]) == prereg_rule.get('microstructure_relation_to_signal_equals')
                and target_fit == prereg_rule.get('volatility_target_fit_equals')
                and stop_fit == prereg_rule.get('volatility_stop_fit_equals')
            ):
                count += 1
        candidate_counts[str(horizon)] = count

    blockers = []
    if duplicate_ids:
        blockers.append('DUPLICATE_FROZEN_FEATURE_IDS')
    if len(common_ids) < min_total:
        blockers.append('MIN_FROZEN_COMMON_COHORT_NOT_REACHED')
    for horizon in horizons:
        if candidate_counts.get(str(horizon), 0) < min_cell_total:
            blockers.append(f'MIN_FROZEN_H1_CANDIDATES_NOT_REACHED_{horizon}H')

    ready = not blockers
    return {
        'version': VERSION,
        'status': 'READY_FOR_CANONICAL_OUTCOME_READ' if ready else 'COLLECTING_PRE_OUTCOME',
        'outcome_access_allowed': ready,
        'outcomes_read': False,
        'performance_metrics_computed': False,
        'matched_frozen_total': len(common_ids),
        'minimum_frozen_common_required': min_total,
        'candidate_frozen_by_horizon': candidate_counts,
        'minimum_h1_candidates_per_horizon_required': min_cell_total,
        'eligible_volatility_horizons_h': horizons,
        'duplicate_frozen_feature_ids': duplicate_ids,
        'research_only': True,
        'can_override_production': False,
        'gate_promoted': False,
        'blockers': blockers,
    }
