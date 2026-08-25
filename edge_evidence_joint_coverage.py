"""ATLAS frozen cross-layer joint-cell coverage audit.

This is a precondition audit for any future interaction research. It measures
whether layer-specific frozen categorical outputs form joint cells with enough
forward observations to support later, separately-approved validation.

It deliberately does NOT read outcomes, test performance, search rules, assign
weights, choose a trade horizon, create a composite score, or alter Production.
Sparse joint cells are a research-design blocker only, never a Production gate.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import edge_evidence_overlap
import edge_evidence_redundancy

VERSION = 'EDGE_EVIDENCE_JOINT_COVERAGE_V1_OUTCOME_FREE'
MIN_MATCHED_OBSERVATIONS = 30
MIN_CELL_N = 10
MAX_CELL_SHARE_PCT = 65.0
MIN_WELL_POPULATED_CELLS = 2
VOLATILITY_HORIZONS_H = (1, 4, 12)


def _read(path, schema):
    path = Path(path)
    out = {}
    if not path.exists():
        return out
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get('schema') != schema:
                continue
            if row.get('production_signal_qualified') is not True:
                continue
            if row.get('research_sample') is True:
                continue
            fid = row.get('forward_id')
            if not fid:
                continue
            out.setdefault(str(fid), row)
    return out


def _profit_label(row):
    return edge_evidence_redundancy._profit_label(row)


def _micro_label(row):
    return edge_evidence_redundancy._micro_label(row)


def _vol_label(row, horizon_h):
    return edge_evidence_redundancy._vol_label(row, horizon_h)


def _cell_report(counter, n):
    rows = [
        {'cell': list(cell), 'n': count, 'share_pct': round(count / n * 100.0, 4) if n else None}
        for cell, count in counter.most_common()
    ]
    well = [row for row in rows if row['n'] >= MIN_CELL_N]
    top_share = rows[0]['share_pct'] if rows else None
    return {
        'unique_joint_cells': len(rows),
        'well_populated_cells': len(well),
        'minimum_cell_n': MIN_CELL_N,
        'top_cell_share_pct': top_share,
        'top_cell_overconcentrated': bool(top_share is not None and top_share > MAX_CELL_SHARE_PCT),
        'cells': rows,
    }


def audit(data_dir):
    data_dir = Path(data_dir)
    overlap = edge_evidence_overlap.audit(data_dir)
    comparable = bool(
        overlap.get('status') == 'COHORTS_IDENTICAL'
        and int(overlap.get('union_unique_forward_ids') or 0) > 0
    )
    base = {
        'version': VERSION,
        'overlap_status': overlap.get('status'),
        'cohort_comparable': comparable,
        'minimum_matched_observations': MIN_MATCHED_OBSERVATIONS,
        'minimum_cell_n': MIN_CELL_N,
        'maximum_single_cell_share_pct': MAX_CELL_SHARE_PCT,
        'minimum_well_populated_cells': MIN_WELL_POPULATED_CELLS,
        'volatility_horizons_evaluated_h': list(VOLATILITY_HORIZONS_H),
        'chosen_trade_horizon_assumed': False,
        'outcomes_read': False,
        'performance_metrics_computed': False,
        'rules_searched': False,
        'grid_search_performed': False,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'cross_layer_interaction_filtering_enabled': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'research_only': True,
        'method': 'OUTCOME_FREE_FROZEN_JOINT_CATEGORICAL_CELL_PREVALENCE',
    }
    if not comparable:
        return {
            **base,
            'status': 'COLLECTING' if overlap.get('status') == 'COLLECTING' else 'COHORT_NOT_COMPARABLE',
            'matched_forward_ids': int(overlap.get('three_way_intersection_unique_forward_ids') or 0),
            'horizon_coverage': {},
            'future_interaction_validation_supported': False,
            'blockers': ['IDENTICAL_FROZEN_SIGNAL_COHORT_REQUIRED'] + list(overlap.get('blockers') or []),
        }

    rows = {
        layer: _read(data_dir / edge_evidence_overlap.FILES[layer], edge_evidence_overlap.SCHEMAS[layer])
        for layer in ('profit_engine', 'microstructure', 'volatility')
    }
    ids = sorted(set(rows['profit_engine']) & set(rows['microstructure']) & set(rows['volatility']))
    horizon_coverage = {}
    blockers = []

    if len(ids) < MIN_MATCHED_OBSERVATIONS:
        blockers.append('INSUFFICIENT_MATCHED_FROZEN_OBSERVATIONS')

    for horizon in VOLATILITY_HORIZONS_H:
        counter = Counter()
        insufficient_vol = 0
        for fid in ids:
            p = _profit_label(rows['profit_engine'][fid])
            m = _micro_label(rows['microstructure'][fid])
            v = _vol_label(rows['volatility'][fid], horizon)
            if v == 'INSUFFICIENT':
                insufficient_vol += 1
            counter[(p, m, v)] += 1
        report = _cell_report(counter, len(ids))
        report['horizon_h'] = horizon
        report['matched_forward_ids'] = len(ids)
        report['volatility_insufficient_rows'] = insufficient_vol
        report['volatility_insufficient_pct'] = round(insufficient_vol / len(ids) * 100.0, 4) if ids else None
        report['coverage_sufficient_for_future_interaction_test'] = bool(
            len(ids) >= MIN_MATCHED_OBSERVATIONS
            and report['well_populated_cells'] >= MIN_WELL_POPULATED_CELLS
            and not report['top_cell_overconcentrated']
        )
        horizon_coverage[str(horizon)] = report
        if report['well_populated_cells'] < MIN_WELL_POPULATED_CELLS:
            blockers.append(f'H{horizon}:TOO_FEW_WELL_POPULATED_JOINT_CELLS')
        if report['top_cell_overconcentrated']:
            blockers.append(f'H{horizon}:JOINT_CELL_DISTRIBUTION_OVERCONCENTRATED')

    supported_horizons = [
        int(h) for h, report in horizon_coverage.items()
        if report.get('coverage_sufficient_for_future_interaction_test')
    ]
    status = 'DESIGN_READ_AVAILABLE' if len(ids) >= MIN_MATCHED_OBSERVATIONS else 'COLLECTING'
    if len(ids) >= MIN_MATCHED_OBSERVATIONS and not supported_horizons:
        status = 'SPARSE_INTERACTION_DESIGN'

    return {
        **base,
        'status': status,
        'matched_forward_ids': len(ids),
        'horizon_coverage': horizon_coverage,
        'horizons_with_sufficient_joint_coverage_h': supported_horizons,
        'future_interaction_validation_supported': bool(supported_horizons),
        'interaction_rule_selection_allowed': False,
        'interaction_outcome_testing_performed': False,
        'blockers': blockers,
    }


def install(collector):
    """Expose a read-only outcome-free design audit without wrapping Production."""
    if getattr(collector, '_EDGE_EVIDENCE_JOINT_COVERAGE_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_JOINT_COVERAGE_STATE', {})
    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    data_dir = Path(getattr(collector, 'DATA', Path('.')))
    state = {
        'enabled': True,
        'version': VERSION,
        'read_only': True,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'report': audit(data_dir),
    }

    def refresh():
        state['report'] = audit(data_dir)
        return state['report']

    collector.EDGE_EVIDENCE_JOINT_COVERAGE_STATE = state
    collector.edge_evidence_joint_coverage_refresh = refresh
    collector._EDGE_EVIDENCE_JOINT_COVERAGE_INSTALLED = True
    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('joint coverage audit mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('joint coverage audit mutated forward_observe')
    return state
