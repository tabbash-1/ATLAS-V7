"""ATLAS preregistered cross-layer interaction outcome validator.

Research-only evaluator for the single immutable H1 interaction hypothesis. The
validator is deliberately fail-closed: it MUST verify the preregistered protocol,
validator guard, and rule manifest before it calls the supplied outcome loader.

It never searches rules, thresholds, cells or horizons. Every preregistered
volatility horizon is reported independently using three chronological,
non-shuffled folds. OPEN/AMBIGUOUS/non-R settlements are excluded rather than
assigned synthetic outcomes.
"""

from __future__ import annotations

import math
from statistics import median

import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules

VERSION = 'EDGE_EVIDENCE_INTERACTION_OUTCOME_VALIDATOR_V2_HASH_BOUND_H1'


def _fid(row):
    return str((row or {}).get('forward_id') or '').strip() or None


def _eligible_frozen(row):
    return bool(
        isinstance(row, dict)
        and row.get('production_signal_qualified') is True
        and row.get('research_sample') is not True
        and _fid(row)
    )


def _index(rows):
    out = {}
    duplicates = set()
    for row in rows or []:
        if not _eligible_frozen(row):
            continue
        fid = _fid(row)
        if fid in out:
            duplicates.add(fid)
        else:
            out[fid] = row
    for fid in duplicates:
        out.pop(fid, None)
    return out, sorted(duplicates)


def _profit_relation(row):
    pe = (row or {}).get('profit_engine')
    rg = pe.get('regime_gate') if isinstance(pe, dict) else None
    return rg.get('reason') if isinstance(rg, dict) else None


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


def _settlement_is_usable(row):
    if not isinstance(row, dict):
        return False
    if not _fid(row):
        return False
    if row.get('terminal') is not True:
        return False
    outcome = str(row.get('path_outcome') or '').upper()
    if outcome in ('OPEN', 'AMBIGUOUS', ''):
        return False
    try:
        r = float(row.get('r_multiple'))
    except Exception:
        return False
    return math.isfinite(r)


def _captured_ms(settlement, feature_rows):
    values = [
        (settlement or {}).get('captured_at_ms'),
        (settlement or {}).get('forward_captured_at_ms'),
    ]
    for row in feature_rows:
        values.extend([
            (row or {}).get('captured_at_ms'),
            (row or {}).get('forward_captured_at_ms'),
        ])
    for value in values:
        try:
            return int(value)
        except Exception:
            pass
    return None


def _max_drawdown_r(values):
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += float(value)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _metrics(items):
    rs = [float(x['r_multiple']) for x in items]
    n = len(rs)
    if not n:
        return {
            'n': 0,
            'average_r': None,
            'median_r': None,
            'win_rate': None,
            'max_drawdown_r': None,
        }
    return {
        'n': n,
        'average_r': sum(rs) / n,
        'median_r': median(rs),
        'win_rate': sum(1 for r in rs if r > 0) / n,
        'max_drawdown_r': _max_drawdown_r(rs),
    }


def _folds(items, count):
    ordered = sorted(items, key=lambda x: (x['captured_at_ms'], x['forward_id']))
    n = len(ordered)
    result = []
    for i in range(count):
        start = (i * n) // count
        end = ((i + 1) * n) // count
        result.append(ordered[start:end])
    return result


def _authorized(protocol_manifest, guard_report, rules_manifest):
    blockers = []
    p = protocol_manifest if isinstance(protocol_manifest, dict) else {}
    g = guard_report if isinstance(guard_report, dict) else {}
    rm = rules_manifest if isinstance(rules_manifest, dict) else {}
    protocol_hash = p.get('protocol_hash')

    if not protocol.verify_manifest(p):
        blockers.append('PROTOCOL_HASH_INVALID')
    if p.get('status') != 'PREREGISTERED':
        blockers.append('PROTOCOL_NOT_PREREGISTERED')
    if g.get('status') != 'VALIDATOR_ARMED':
        blockers.append('VALIDATOR_GUARD_NOT_ARMED')
    if g.get('armed_protocol_hash') != protocol_hash:
        blockers.append('GUARD_PROTOCOL_HASH_MISMATCH')
    if rm.get('status') != 'PREREGISTERED':
        blockers.append('RULES_NOT_PREREGISTERED')
    if not rules.verify_manifest(rm, p):
        blockers.append('RULES_HASH_OR_PARENT_INVALID')
    if rm.get('rule_count') != 1 or len(rm.get('rules') or []) != 1:
        blockers.append('EXACTLY_ONE_PREREGISTERED_RULE_REQUIRED')
    if sorted(rm.get('eligible_volatility_horizons_h') or []) != sorted(p.get('eligible_volatility_horizons_h') or []):
        blockers.append('RULE_AND_PROTOCOL_HORIZONS_DIFFER')
    return not blockers, blockers


def _blocked(blockers):
    return {
        'version': VERSION,
        'status': 'BLOCKED',
        'validator_execution_started': False,
        'outcomes_read': False,
        'interaction_outcome_testing_performed': False,
        'performance_metrics_computed': False,
        'validated_research_hypothesis': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'rule_search_performed': False,
        'horizon_selection_performed': False,
        'research_only': True,
        'blockers': list(blockers),
        'horizons': {},
    }


def validate(protocol_manifest, guard_report, rules_manifest, profit_rows, micro_rows, volatility_rows, outcome_loader):
    """Validate H1 only. Outcome loader is never called before authorization."""
    authorized, blockers = _authorized(protocol_manifest, guard_report, rules_manifest)
    if not authorized:
        return _blocked(blockers)

    # Authorization is complete; only now may canonical outcomes be read.
    settlements = outcome_loader()
    if not isinstance(settlements, (list, tuple)):
        result = _blocked(['OUTCOME_LOADER_DID_NOT_RETURN_SEQUENCE'])
        result['validator_execution_started'] = True
        result['outcomes_read'] = True
        return result

    pmap, pdup = _index(profit_rows)
    mmap, mdup = _index(micro_rows)
    vmap, vdup = _index(volatility_rows)
    duplicate_ids = sorted(set(pdup) | set(mdup) | set(vdup))
    common_ids = set(pmap) & set(mmap) & set(vmap)

    settlement_map = {}
    settlement_duplicates = set()
    excluded_settlements = 0
    for row in settlements:
        fid = _fid(row)
        if not _settlement_is_usable(row) or fid not in common_ids:
            excluded_settlements += 1
            continue
        if fid in settlement_map:
            settlement_duplicates.add(fid)
        else:
            settlement_map[fid] = row
    for fid in settlement_duplicates:
        settlement_map.pop(fid, None)

    joined = []
    missing_timestamp = 0
    for fid, settlement in settlement_map.items():
        feature_rows = (pmap[fid], mmap[fid], vmap[fid])
        ts = _captured_ms(settlement, feature_rows)
        if ts is None:
            missing_timestamp += 1
            continue
        joined.append({
            'forward_id': fid,
            'captured_at_ms': ts,
            'r_multiple': float(settlement['r_multiple']),
            'path_outcome': settlement.get('path_outcome'),
            'profit_relation': _profit_relation(pmap[fid]),
            'micro_relation': _micro_relation(mmap[fid]),
            'volatility_row': vmap[fid],
        })
    joined.sort(key=lambda x: (x['captured_at_ms'], x['forward_id']))

    mins = (protocol_manifest or {}).get('minimum_samples') or {}
    min_total = int(mins.get('total_settled') or 0)
    min_cell_fold = int(mins.get('cell_settled_per_fold') or 0)
    min_cell_total = int(mins.get('total_settled_per_cell') or 0)
    min_base_fold = int(mins.get('baseline_settled_per_fold') or 0)
    fold_count = int(((protocol_manifest or {}).get('split_policy') or {}).get('fold_count') or 0)
    prereg_rule = (rules_manifest.get('rules') or [])[0]

    top_blockers = []
    if duplicate_ids:
        top_blockers.append('DUPLICATE_FROZEN_FEATURE_IDS')
    if settlement_duplicates:
        top_blockers.append('DUPLICATE_SETTLEMENT_IDS')
    if fold_count != 3:
        top_blockers.append('FROZEN_PROTOCOL_REQUIRES_THREE_FOLDS')
    if len(joined) < min_total:
        top_blockers.append('MIN_TOTAL_SETTLED_NOT_REACHED')

    horizon_reports = {}
    horizons = sorted(int(x) for x in protocol_manifest.get('eligible_volatility_horizons_h') or [])
    for horizon in horizons:
        baseline = list(joined)
        candidate = []
        for item in joined:
            target_fit, stop_fit = _vol_fit(item['volatility_row'], horizon)
            if (
                item['profit_relation'] == prereg_rule['profit_regime_relation_equals']
                and item['micro_relation'] == prereg_rule['microstructure_relation_to_signal_equals']
                and target_fit == prereg_rule['volatility_target_fit_equals']
                and stop_fit == prereg_rule['volatility_stop_fit_equals']
            ):
                candidate.append(item)

        h_blockers = list(top_blockers)
        if len(candidate) < min_cell_total:
            h_blockers.append('MIN_TOTAL_SETTLED_PER_RULE_CELL_NOT_REACHED')

        baseline_folds = _folds(baseline, fold_count) if fold_count > 0 else []
        fold_reports = []
        all_fold_pass = True
        for i, base_fold in enumerate(baseline_folds):
            ids = {x['forward_id'] for x in base_fold}
            cand_fold = [x for x in candidate if x['forward_id'] in ids]
            bm = _metrics(base_fold)
            cm = _metrics(cand_fold)
            sample_ok = bm['n'] >= min_base_fold and cm['n'] >= min_cell_fold
            avg_delta = None if not sample_ok else cm['average_r'] - bm['average_r']
            win_delta = None if not sample_ok else cm['win_rate'] - bm['win_rate']
            median_delta = None if not sample_ok else cm['median_r'] - bm['median_r']
            drawdown_delta = None if not sample_ok else cm['max_drawdown_r'] - bm['max_drawdown_r']
            fold_pass = bool(sample_ok and avg_delta > 0 and drawdown_delta <= 0)
            all_fold_pass = all_fold_pass and fold_pass
            fold_reports.append({
                'fold': i + 1,
                'sample_requirements_met': sample_ok,
                'baseline': bm,
                'candidate': cm,
                'average_r_delta_vs_baseline': avg_delta,
                'win_rate_delta_vs_baseline': win_delta,
                'median_r_delta_vs_baseline': median_delta,
                'max_drawdown_r_delta_vs_baseline': drawdown_delta,
                'primary_metric_positive': bool(avg_delta is not None and avg_delta > 0),
                'drawdown_not_worse': bool(drawdown_delta is not None and drawdown_delta <= 0),
                'pass': fold_pass,
            })

        if any(not f['sample_requirements_met'] for f in fold_reports):
            h_blockers.append('ONE_OR_MORE_FOLDS_INSUFFICIENT')
        if not all_fold_pass and all(f['sample_requirements_met'] for f in fold_reports):
            h_blockers.append('ONE_OR_MORE_FOLDS_FAILED_PREREGISTERED_CRITERIA')

        validated = bool(not h_blockers and all_fold_pass and len(fold_reports) == fold_count)
        horizon_reports[str(horizon)] = {
            'horizon_h': horizon,
            'status': 'VALIDATED' if validated else ('COLLECTING' if any('MIN_' in b or 'INSUFFICIENT' in b for b in h_blockers) else 'FAILED'),
            'rule_id': prereg_rule.get('rule_id'),
            'baseline_total': len(baseline),
            'candidate_total': len(candidate),
            'folds': fold_reports,
            'validated_research_hypothesis': validated,
            'blockers': sorted(set(h_blockers)),
        }

    all_horizons_validated = bool(horizon_reports and all(x['validated_research_hypothesis'] for x in horizon_reports.values()))
    any_collecting = any(x['status'] == 'COLLECTING' for x in horizon_reports.values())
    overall_status = 'VALIDATED_RESEARCH_ONLY' if all_horizons_validated else ('COLLECTING' if any_collecting else 'FAILED_RESEARCH_HYPOTHESIS')

    return {
        'version': VERSION,
        'status': overall_status,
        'validator_execution_started': True,
        'outcomes_read': True,
        'interaction_outcome_testing_performed': True,
        'performance_metrics_computed': True,
        'protocol_hash': protocol_manifest.get('protocol_hash'),
        'rules_hash': rules_manifest.get('rules_hash'),
        'rule_id': prereg_rule.get('rule_id'),
        'chronological_folds': fold_count,
        'settled_joined_total': len(joined),
        'excluded_settlements': excluded_settlements,
        'missing_timestamp_rows': missing_timestamp,
        'duplicate_frozen_feature_ids': duplicate_ids,
        'duplicate_settlement_ids': sorted(settlement_duplicates),
        'validated_research_hypothesis': all_horizons_validated,
        'all_eligible_horizons_must_pass': True,
        'horizon_selection_performed': False,
        'rule_search_performed': False,
        'threshold_tuning_performed': False,
        'grid_search_performed': False,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'research_only': True,
        'blockers': sorted(set(top_blockers)),
        'horizons': horizon_reports,
    }
