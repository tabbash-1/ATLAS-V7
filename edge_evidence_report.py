"""ATLAS independent shadow-edge evidence aggregator.

Summarizes already-produced prequential walk-forward reports from Profit Engine,
Microstructure and Volatility and the frozen-signal cohort overlap audit. It does
not combine predictions, assign weights, score trades, recompute historical
evidence, or alter Production.

MULTI_LAYER_EVIDENCE_AVAILABLE requires both independent layer support and a
comparable frozen forward_id cohort. It is still only a research/governance
statement: never a live-trading approval and never a gate promotion.
"""

from __future__ import annotations

import edge_evidence_overlap

VERSION = 'EDGE_EVIDENCE_REPORT_V2_WITH_COHORT_COMPARABILITY'
LAYERS = ('profit_engine', 'microstructure', 'volatility')


def _dict(value):
    return value if isinstance(value, dict) else {}


def _profit_layer(state):
    available = bool(state)
    report = _dict(_dict(state).get('walk_forward_report'))
    status = report.get('status') or ('UNAVAILABLE' if not available else 'COLLECTING')
    supported = bool(
        available
        and status == 'VALIDATION_READ_AVAILABLE'
        and report.get('improves_production_expectancy') is True
    )
    blockers = list(report.get('blockers') or [])
    if not available:
        blockers = ['PROFIT_ENGINE_RUNTIME_UNAVAILABLE']
    elif not supported and not blockers:
        blockers = ['PROFIT_ENGINE_EDGE_NOT_YET_SUPPORTED']
    return {
        'available': available,
        'status': status,
        'evidence_supported': supported,
        'frozen_observations': report.get('frozen_observations'),
        'settled_joined': report.get('settled_joined'),
        'canonical_execution_rows': report.get('canonical_execution_rows'),
        'average_r_delta': report.get('delta_average_r'),
        'drawdown_improvement_r': report.get('drawdown_improvement_r'),
        'blockers': blockers,
        'source_version': report.get('version'),
    }


def _microstructure_layer(state):
    available = bool(state)
    report = _dict(_dict(state).get('walk_forward_report'))
    status = report.get('status') or ('UNAVAILABLE' if not available else 'COLLECTING')
    supported = bool(
        available
        and status == 'VALIDATION_READ_AVAILABLE'
        and report.get('evidence_supports_future_gate') is True
    )
    blockers = list(report.get('blockers') or [])
    if not available:
        blockers = ['MICROSTRUCTURE_RUNTIME_UNAVAILABLE']
    elif not supported and not blockers:
        blockers = ['MICROSTRUCTURE_EDGE_NOT_YET_SUPPORTED']
    return {
        'available': available,
        'status': status,
        'evidence_supported': supported,
        'frozen_observations': report.get('frozen_observations'),
        'settled_joined': report.get('settled_joined'),
        'canonical_execution_rows': report.get('canonical_execution_rows'),
        'aligned_average_r_delta': report.get('aligned_average_r_delta_vs_baseline'),
        'opposed_average_r_delta': report.get('opposed_average_r_delta_vs_baseline'),
        'blockers': blockers,
        'source_version': report.get('version'),
    }


def _volatility_layer(state):
    available = bool(state)
    report = _dict(_dict(state).get('report'))
    status = report.get('status') or ('UNAVAILABLE' if not available else 'COLLECTING')
    horizons = [int(x) for x in (report.get('horizons_supporting_future_filter') or [])]
    supported = bool(
        available
        and status == 'VALIDATION_READ_AVAILABLE'
        and horizons
    )
    blockers = list(report.get('blockers') or [])
    if not available:
        blockers = ['VOLATILITY_WALKFORWARD_RUNTIME_UNAVAILABLE']
    elif not supported and not blockers:
        blockers = ['VOLATILITY_GEOMETRY_EDGE_NOT_YET_SUPPORTED']
    return {
        'available': available,
        'status': status,
        'evidence_supported': supported,
        'frozen_observations': report.get('frozen_observations'),
        'settled_joined': report.get('settled_joined'),
        'canonical_execution_rows': report.get('canonical_execution_rows'),
        'supported_horizons_h': horizons,
        'chosen_trade_horizon_assumed': bool(report.get('chosen_trade_horizon_assumed')),
        'blockers': blockers,
        'source_version': report.get('version'),
    }


def _overlap_report(overlap_state):
    if not overlap_state:
        return {
            'available': False,
            'status': 'UNAVAILABLE',
            'cohorts_comparable': False,
            'blockers': ['EDGE_EVIDENCE_OVERLAP_AUDIT_UNAVAILABLE'],
        }
    report = _dict(_dict(overlap_state).get('report'))
    status = report.get('status') or 'COLLECTING'
    comparable = bool(status == 'COHORTS_IDENTICAL' and report.get('union_unique_forward_ids', 0) > 0)
    blockers = list(report.get('blockers') or [])
    if not comparable and not blockers:
        blockers = ['FROZEN_SIGNAL_COHORTS_NOT_COMPARABLE']
    return {
        'available': True,
        'status': status,
        'cohorts_comparable': comparable,
        'union_unique_forward_ids': report.get('union_unique_forward_ids'),
        'three_way_intersection_unique_forward_ids': report.get('three_way_intersection_unique_forward_ids'),
        'three_way_overlap_pct_of_union': report.get('three_way_overlap_pct_of_union'),
        'missing_forward_id_counts_by_layer': report.get('missing_forward_id_counts_by_layer') or {},
        'duplicate_layers': report.get('duplicate_layers') or [],
        'missing_files': report.get('missing_files') or [],
        'blockers': blockers,
        'source_version': report.get('version'),
    }


def aggregate(profit_state=None, microstructure_state=None, volatility_walkforward_state=None, overlap_state=None):
    layers = {
        'profit_engine': _profit_layer(profit_state),
        'microstructure': _microstructure_layer(microstructure_state),
        'volatility': _volatility_layer(volatility_walkforward_state),
    }
    overlap = _overlap_report(overlap_state)
    supported = [name for name, row in layers.items() if row['evidence_supported']]
    unavailable = [name for name, row in layers.items() if not row['available']]

    canonical_counts = {
        name: row.get('canonical_execution_rows')
        for name, row in layers.items()
        if row.get('canonical_execution_rows') is not None
    }
    distinct_counts = sorted(set(canonical_counts.values()))
    canonical_consistent = len(distinct_counts) <= 1

    blockers = []
    for name, row in layers.items():
        for blocker in row.get('blockers') or []:
            blockers.append(f'{name.upper()}:{blocker}')
    if not canonical_consistent:
        blockers.append('CANONICAL_EXECUTION_COUNT_MISMATCH_ACROSS_LAYER_REPORTS')
    for blocker in overlap.get('blockers') or []:
        blockers.append(f'COHORT_OVERLAP:{blocker}')

    all_layers_supported = len(supported) == len(LAYERS)
    if all_layers_supported and canonical_consistent and overlap['cohorts_comparable']:
        status = 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    elif supported:
        status = 'PARTIAL_EVIDENCE'
    else:
        status = 'COLLECTING'

    return {
        'version': VERSION,
        'status': status,
        'layers': layers,
        'cohort_overlap': overlap,
        'supported_layers': supported,
        'supported_layer_count': len(supported),
        'total_layer_count': len(LAYERS),
        'unavailable_layers': unavailable,
        'canonical_execution_rows_by_layer': canonical_counts,
        'canonical_execution_count_consistent': canonical_consistent,
        'frozen_signal_cohorts_comparable': overlap['cohorts_comparable'],
        'blockers': blockers,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'cross_layer_interaction_filtering_enabled': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'research_only': True,
        'method': 'INDEPENDENT_PREQUENTIAL_LAYER_READINESS_PLUS_FROZEN_COHORT_COMPARABILITY_WITHOUT_COMPOSITE_WEIGHTING',
    }


def from_collector(collector):
    return aggregate(
        getattr(collector, 'PROFIT_ENGINE_RUNTIME_STATE', None),
        getattr(collector, 'MICROSTRUCTURE_RUNTIME_STATE', None),
        getattr(collector, 'VOLATILITY_WALKFORWARD_RUNTIME_STATE', None),
        getattr(collector, 'EDGE_EVIDENCE_OVERLAP_STATE', None),
    )


def install(collector):
    """Expose read-only governance reports; never wrap Production functions."""
    if getattr(collector, '_EDGE_EVIDENCE_REPORT_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_REPORT_STATE', {})

    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    edge_evidence_overlap.install(collector)
    state = {
        'enabled': True,
        'version': VERSION,
        'read_only': True,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'report': from_collector(collector),
    }

    def refresh():
        overlap_refresh = getattr(collector, 'edge_evidence_overlap_refresh', None)
        if callable(overlap_refresh):
            overlap_refresh()
        state['report'] = from_collector(collector)
        return state['report']

    collector.EDGE_EVIDENCE_REPORT_STATE = state
    collector.edge_evidence_refresh = refresh
    collector._EDGE_EVIDENCE_REPORT_INSTALLED = True

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('edge evidence report mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('edge evidence report mutated forward_observe')
    return state
