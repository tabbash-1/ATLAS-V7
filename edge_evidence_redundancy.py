"""ATLAS frozen shadow-layer redundancy audit.

Measures descriptive association between layer-specific outputs captured before
outcomes were known. It deliberately excludes shared Production fields such as
signal direction, entry and score, because correlation in those fields would be
mechanical rather than evidence that the research layers are redundant.

The audit reads only the identical Production-qualified forward_id cohort from
Profit Engine, Microstructure and Volatility frozen sidecars. It never reads
outcomes, assigns weights, creates a composite score, chooses a trade horizon or
changes Production.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import edge_evidence_overlap

VERSION = 'EDGE_EVIDENCE_REDUNDANCY_V1_FROZEN_LAYER_OUTPUT_ASSOCIATION'
MIN_MATCHED_OBSERVATIONS = 20
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
            if row.get('production_signal_qualified') is not True or row.get('research_sample') is True:
                continue
            fid = row.get('forward_id')
            if not fid:
                continue
            # Duplicate forward_ids are intentionally not silently resolved. The
            # overlap audit will mark the cohort non-comparable and this audit
            # will fail closed before association is interpreted.
            out.setdefault(str(fid), row)
    return out


def _cramers_v(xs, ys):
    pairs = [(str(x), str(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 2:
        return None
    x_levels = sorted({x for x, _ in pairs})
    y_levels = sorted({y for _, y in pairs})
    if len(x_levels) < 2 or len(y_levels) < 2:
        return None
    row_totals = Counter(x for x, _ in pairs)
    col_totals = Counter(y for _, y in pairs)
    cells = Counter(pairs)
    chi2 = 0.0
    for x in x_levels:
        for y in y_levels:
            expected = row_totals[x] * col_totals[y] / n
            if expected > 0:
                chi2 += (cells[(x, y)] - expected) ** 2 / expected
    denom = n * min(len(x_levels) - 1, len(y_levels) - 1)
    if denom <= 0:
        return None
    return math.sqrt(max(0.0, chi2 / denom))


def _strength(v):
    if v is None:
        return 'UNDEFINED'
    if v < 0.30:
        return 'LOW_OBSERVED_ASSOCIATION'
    if v < 0.60:
        return 'MODERATE_OBSERVED_ASSOCIATION'
    return 'HIGH_OBSERVED_ASSOCIATION'


def _profit_label(row):
    shadow = (row or {}).get('profit_engine') or {}
    regime_gate = shadow.get('regime_gate') or {}
    # Use layer-specific independent regime context, not the final WAIT/LONG/SHORT
    # decision which can be dominated by calibration warm-up.
    return regime_gate.get('reason') or 'UNKNOWN_PROFIT_REGIME_RELATION'


def _micro_label(row):
    return (row or {}).get('relation_to_signal') or 'MIXED_OR_INSUFFICIENT'


def _vol_label(row, horizon_h):
    fits = (row or {}).get('geometry_fit_by_horizon') or {}
    fit = fits.get(str(int(horizon_h))) or fits.get(str(horizon_h)) or {}
    if fit.get('status') != 'READY':
        return 'INSUFFICIENT'
    target = fit.get('target_fit') or 'UNKNOWN_TARGET_FIT'
    stop = fit.get('stop_fit') or 'UNKNOWN_STOP_FIT'
    return f'{target}|{stop}'


def _association(name, xs, ys):
    usable = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    v = _cramers_v([x for x, _ in usable], [y for _, y in usable])
    return {
        'pair': name,
        'n': len(usable),
        'cramers_v': round(v, 6) if v is not None else None,
        'observed_association_strength': _strength(v),
        'x_unique_labels': len({x for x, _ in usable}),
        'y_unique_labels': len({y for _, y in usable}),
        'statistical_independence_claimed': False,
        'causal_independence_claimed': False,
    }


def audit(data_dir):
    data_dir = Path(data_dir)
    overlap = edge_evidence_overlap.audit(data_dir)
    comparable = overlap.get('status') == 'COHORTS_IDENTICAL' and int(overlap.get('union_unique_forward_ids') or 0) > 0

    base = {
        'version': VERSION,
        'overlap_status': overlap.get('status'),
        'cohort_comparable': comparable,
        'matched_forward_ids': int(overlap.get('three_way_intersection_unique_forward_ids') or 0),
        'minimum_matched_observations': MIN_MATCHED_OBSERVATIONS,
        'shared_production_fields_excluded': ['direction', 'entry', 'score', 'signal_threshold'],
        'chosen_trade_horizon_assumed': False,
        'volatility_horizons_evaluated_h': list(VOLATILITY_HORIZONS_H),
        'outcomes_read': False,
        'historical_features_recomputed': False,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'cross_layer_interaction_filtering_enabled': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'statistical_independence_claimed': False,
        'research_only': True,
        'method': 'CRAMERS_V_ON_LAYER_SPECIFIC_FROZEN_CATEGORICAL_OUTPUTS_ONLY',
    }
    if not comparable:
        return {
            **base,
            'status': 'COLLECTING' if overlap.get('status') == 'COLLECTING' else 'COHORT_NOT_COMPARABLE',
            'associations': {},
            'blockers': ['IDENTICAL_FROZEN_SIGNAL_COHORT_REQUIRED'] + list(overlap.get('blockers') or []),
        }

    rows = {
        layer: _read(data_dir / edge_evidence_overlap.FILES[layer], edge_evidence_overlap.SCHEMAS[layer])
        for layer in ('profit_engine', 'microstructure', 'volatility')
    }
    ids = sorted(set(rows['profit_engine']) & set(rows['microstructure']) & set(rows['volatility']))
    profit_labels = [_profit_label(rows['profit_engine'][fid]) for fid in ids]
    micro_labels = [_micro_label(rows['microstructure'][fid]) for fid in ids]

    associations = {
        'profit_vs_microstructure': _association(
            'profit_vs_microstructure', profit_labels, micro_labels
        )
    }
    for horizon in VOLATILITY_HORIZONS_H:
        vol_labels = [_vol_label(rows['volatility'][fid], horizon) for fid in ids]
        associations[f'profit_vs_volatility_{horizon}h'] = _association(
            f'profit_vs_volatility_{horizon}h', profit_labels, vol_labels
        )
        associations[f'microstructure_vs_volatility_{horizon}h'] = _association(
            f'microstructure_vs_volatility_{horizon}h', micro_labels, vol_labels
        )

    blockers = []
    if len(ids) < MIN_MATCHED_OBSERVATIONS:
        blockers.append('INSUFFICIENT_MATCHED_FROZEN_OBSERVATIONS')
    undefined = [name for name, row in associations.items() if row.get('cramers_v') is None]
    if undefined:
        blockers.append('ASSOCIATION_UNDEFINED_FOR_ONE_OR_MORE_PAIRS')

    high = [
        name for name, row in associations.items()
        if row.get('observed_association_strength') == 'HIGH_OBSERVED_ASSOCIATION'
    ]
    status = 'COLLECTING' if blockers else 'DESCRIPTIVE_READ_AVAILABLE'
    return {
        **base,
        'status': status,
        'matched_forward_ids': len(ids),
        'associations': associations,
        'high_observed_association_pairs': high,
        'high_association_is_redundancy_proof': False,
        'low_association_is_independence_proof': False,
        'blockers': blockers,
    }


def install(collector):
    """Expose read-only redundancy diagnostics without wrapping Production."""
    if getattr(collector, '_EDGE_EVIDENCE_REDUNDANCY_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_REDUNDANCY_STATE', {})
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

    collector.EDGE_EVIDENCE_REDUNDANCY_STATE = state
    collector.edge_evidence_redundancy_refresh = refresh
    collector._EDGE_EVIDENCE_REDUNDANCY_INSTALLED = True
    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('edge redundancy audit mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('edge redundancy audit mutated forward_observe')
    return state
