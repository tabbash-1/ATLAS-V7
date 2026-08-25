"""ATLAS frozen-evidence cohort overlap audit.

This module compares only the explicit Production-qualified forward_id universes
captured in the three frozen-at-signal shadow sidecars:
- Profit Engine
- Microstructure
- Volatility Forecast

It does not read outcomes, recompute historical features, score trades, assign
weights, or promote gates. The purpose is statistical governance: independent
layer evidence should be interpreted cautiously when it is based on materially
different signal cohorts.
"""

from __future__ import annotations

import json
from pathlib import Path

VERSION = 'EDGE_EVIDENCE_OVERLAP_V1_FROZEN_SIGNAL_COHORT_AUDIT'

SCHEMAS = {
    'profit_engine': 'ATLAS_PROFIT_ENGINE_OBSERVATION_V1',
    'microstructure': 'ATLAS_MICROSTRUCTURE_OBSERVATION_V1',
    'volatility': 'ATLAS_VOLATILITY_FORECAST_OBSERVATION_V1',
}

FILES = {
    'profit_engine': 'profit_engine_observations.jsonl',
    'microstructure': 'microstructure_observations.jsonl',
    'volatility': 'volatility_forecast_observations.jsonl',
}


def _read_layer(path, schema):
    path = Path(path)
    ids = []
    stats = {
        'file_exists': path.exists(),
        'lines_seen': 0,
        'valid_rows': 0,
        'malformed_rows': 0,
        'wrong_schema_rows': 0,
        'research_or_unqualified_rows_excluded': 0,
        'missing_forward_id_rows': 0,
    }
    if not path.exists():
        return ids, stats

    with path.open(encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            stats['lines_seen'] += 1
            try:
                row = json.loads(line)
            except Exception:
                stats['malformed_rows'] += 1
                continue
            if row.get('schema') != schema:
                stats['wrong_schema_rows'] += 1
                continue
            if row.get('production_signal_qualified') is not True or row.get('research_sample') is True:
                stats['research_or_unqualified_rows_excluded'] += 1
                continue
            forward_id = row.get('forward_id')
            if not forward_id:
                stats['missing_forward_id_rows'] += 1
                continue
            ids.append(str(forward_id))
            stats['valid_rows'] += 1
    return ids, stats


def _layer_summary(ids, stats):
    unique = set(ids)
    duplicates = len(ids) - len(unique)
    return {
        **stats,
        'rows_with_forward_id': len(ids),
        'unique_forward_ids': len(unique),
        'duplicate_forward_id_rows': duplicates,
        'duplicate_free': duplicates == 0,
    }, unique


def audit(data_dir):
    data_dir = Path(data_dir)
    summaries = {}
    sets = {}
    for layer in ('profit_engine', 'microstructure', 'volatility'):
        ids, stats = _read_layer(data_dir / FILES[layer], SCHEMAS[layer])
        summary, unique = _layer_summary(ids, stats)
        summaries[layer] = summary
        sets[layer] = unique

    p = sets['profit_engine']
    m = sets['microstructure']
    v = sets['volatility']
    union = p | m | v
    intersection = p & m & v

    pairwise = {
        'profit_microstructure': len(p & m),
        'profit_volatility': len(p & v),
        'microstructure_volatility': len(m & v),
    }
    missing_by_layer = {
        'profit_engine': sorted((m | v) - p),
        'microstructure': sorted((p | v) - m),
        'volatility': sorted((p | m) - v),
    }

    coverage_pct = {
        layer: round((len(sets[layer] & union) / len(union) * 100.0), 2) if union else None
        for layer in sets
    }
    three_way_coverage_pct = round(len(intersection) / len(union) * 100.0, 2) if union else None

    duplicate_layers = [
        layer for layer, row in summaries.items()
        if row['duplicate_forward_id_rows'] > 0
    ]
    missing_files = [layer for layer, row in summaries.items() if not row['file_exists']]

    blockers = []
    if missing_files:
        blockers.append('FROZEN_EVIDENCE_SIDECAR_MISSING')
    if duplicate_layers:
        blockers.append('DUPLICATE_FORWARD_IDS_IN_FROZEN_EVIDENCE')
    if union and len(intersection) < len(union):
        blockers.append('FROZEN_SIGNAL_COHORTS_NOT_IDENTICAL')
    if not union:
        blockers.append('NO_FROZEN_SIGNAL_COHORT_AVAILABLE')

    # This is intentionally a descriptive governance status, not a statistical
    # threshold for Production promotion.
    status = 'COHORTS_IDENTICAL' if union and intersection == union and not duplicate_layers and not missing_files else 'COHORT_MISMATCH'
    if not union:
        status = 'COLLECTING'

    return {
        'version': VERSION,
        'status': status,
        'layers': summaries,
        'union_unique_forward_ids': len(union),
        'three_way_intersection_unique_forward_ids': len(intersection),
        'three_way_overlap_pct_of_union': three_way_coverage_pct,
        'layer_coverage_pct_of_union': coverage_pct,
        'pairwise_intersection_counts': pairwise,
        'missing_forward_ids_by_layer': missing_by_layer,
        'missing_forward_id_counts_by_layer': {
            layer: len(values) for layer, values in missing_by_layer.items()
        },
        'duplicate_layers': duplicate_layers,
        'missing_files': missing_files,
        'blockers': blockers,
        'outcomes_read': False,
        'historical_features_recomputed': False,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'cross_layer_interaction_filtering_enabled': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'research_only': True,
        'method': 'FROZEN_PRODUCTION_SIGNAL_FORWARD_ID_SET_OVERLAP_ONLY',
    }


def install(collector):
    """Expose read-only cohort audit state without wrapping Production callables."""
    if getattr(collector, '_EDGE_EVIDENCE_OVERLAP_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_OVERLAP_STATE', {})

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

    collector.EDGE_EVIDENCE_OVERLAP_STATE = state
    collector.edge_evidence_overlap_refresh = refresh
    collector._EDGE_EVIDENCE_OVERLAP_INSTALLED = True

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('edge overlap audit mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('edge overlap audit mutated forward_observe')
    return state
