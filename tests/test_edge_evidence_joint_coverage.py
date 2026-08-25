import json
from pathlib import Path
from types import SimpleNamespace

import edge_evidence_joint_coverage as ejc
import edge_evidence_overlap as eeo


def _write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(x) for x in rows) + '\n', encoding='utf-8')


def _profit(fid, label, ts=1):
    return {
        'schema': eeo.SCHEMAS['profit_engine'],
        'forward_id': fid,
        'forward_captured_at_ms': ts,
        'production_signal_qualified': True,
        'research_sample': False,
        'profit_engine': {'regime_gate': {'reason': label}},
    }


def _micro(fid, label, ts=1):
    return {
        'schema': eeo.SCHEMAS['microstructure'],
        'forward_id': fid,
        'forward_captured_at_ms': ts,
        'production_signal_qualified': True,
        'research_sample': False,
        'relation_to_signal': label,
    }


def _vol(fid, labels, ts=1):
    fits = {}
    for h in ejc.VOLATILITY_HORIZONS_H:
        label = labels.get(h)
        if label is None:
            fits[str(h)] = {'status': 'INSUFFICIENT'}
        else:
            target, stop = label
            fits[str(h)] = {'status': 'READY', 'target_fit': target, 'stop_fit': stop}
    return {
        'schema': eeo.SCHEMAS['volatility'],
        'forward_id': fid,
        'forward_captured_at_ms': ts,
        'production_signal_qualified': True,
        'research_sample': False,
        'geometry_fit_by_horizon': fits,
    }


def _populate_balanced(data_dir, n=40):
    profits, micros, vols = [], [], []
    cells = [
        ('REGIME_ALIGNED', 'ALIGNED', ('PLAUSIBLE', 'PLAUSIBLE')),
        ('ASSET_REGIME_NOT_ALIGNED', 'OPPOSED_OR_CROWDED', ('STRETCHED', 'TIGHT')),
        ('REGIME_ALIGNED', 'MIXED_OR_INSUFFICIENT', ('CLOSE', 'WIDE')),
        ('ASSET_REGIME_NOT_ALIGNED', 'ALIGNED', ('PLAUSIBLE', 'WIDE')),
    ]
    for i in range(n):
        fid = f'F{i:03d}'; ts = 1000 + i
        p, m, v = cells[i % len(cells)]
        profits.append(_profit(fid, p, ts))
        micros.append(_micro(fid, m, ts))
        vols.append(_vol(fid, {1: v, 4: v, 12: v}, ts))
    _write(Path(data_dir) / eeo.FILES['profit_engine'], profits)
    _write(Path(data_dir) / eeo.FILES['microstructure'], micros)
    _write(Path(data_dir) / eeo.FILES['volatility'], vols)


def _populate_concentrated(data_dir, n=40):
    profits, micros, vols = [], [], []
    for i in range(n):
        fid = f'F{i:03d}'; ts = 1000 + i
        if i < 30:
            p, m, v = 'REGIME_ALIGNED', 'ALIGNED', ('PLAUSIBLE', 'PLAUSIBLE')
        else:
            p, m, v = 'ASSET_REGIME_NOT_ALIGNED', 'OPPOSED_OR_CROWDED', ('STRETCHED', 'TIGHT')
        profits.append(_profit(fid, p, ts))
        micros.append(_micro(fid, m, ts))
        vols.append(_vol(fid, {1: v, 4: v, 12: v}, ts))
    _write(Path(data_dir) / eeo.FILES['profit_engine'], profits)
    _write(Path(data_dir) / eeo.FILES['microstructure'], micros)
    _write(Path(data_dir) / eeo.FILES['volatility'], vols)


def test_balanced_joint_cells_support_future_interaction_design_but_do_not_test_outcomes(tmp_path):
    _populate_balanced(tmp_path, 40)
    out = ejc.audit(tmp_path)
    assert out['status'] == 'DESIGN_READ_AVAILABLE'
    assert out['matched_forward_ids'] == 40
    assert out['aligned_cohort_comparable'] is True
    assert out['future_interaction_validation_supported'] is True
    assert out['horizons_with_sufficient_joint_coverage_h'] == [1, 4, 12]
    assert out['outcomes_read'] is False
    assert out['performance_metrics_computed'] is False
    assert out['rules_searched'] is False
    assert out['grid_search_performed'] is False
    assert out['chosen_trade_horizon_assumed'] is False
    assert out['interaction_rule_selection_allowed'] is False
    assert out['interaction_outcome_testing_performed'] is False
    assert out['cross_layer_interaction_filtering_enabled'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    for h in ('1', '4', '12'):
        assert out['horizon_coverage'][h]['well_populated_cells'] == 4
        assert out['horizon_coverage'][h]['top_cell_overconcentrated'] is False


def test_too_few_rows_stays_collecting(tmp_path):
    _populate_balanced(tmp_path, 20)
    out = ejc.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['future_interaction_validation_supported'] is False
    assert 'INSUFFICIENT_MATCHED_FROZEN_OBSERVATIONS' in out['blockers']


def test_overconcentrated_cells_are_sparse_design_blocker(tmp_path):
    _populate_concentrated(tmp_path, 40)
    out = ejc.audit(tmp_path)
    assert out['status'] == 'SPARSE_INTERACTION_DESIGN'
    assert out['future_interaction_validation_supported'] is False
    assert out['horizons_with_sufficient_joint_coverage_h'] == []
    for h in ('1', '4', '12'):
        assert out['horizon_coverage'][h]['top_cell_share_pct'] == 75.0
        assert out['horizon_coverage'][h]['top_cell_overconcentrated'] is True


def test_historical_rollout_rows_before_latest_layer_start_do_not_block(tmp_path):
    _populate_balanced(tmp_path, 40)
    p = Path(tmp_path) / eeo.FILES['profit_engine']
    m = Path(tmp_path) / eeo.FILES['microstructure']
    profit_rows = [json.loads(x) for x in p.read_text().splitlines()]
    micro_rows = [json.loads(x) for x in m.read_text().splitlines()]
    profit_rows.insert(0, _profit('P_OLD', 'REGIME_ALIGNED', 100))
    micro_rows.insert(0, _micro('M_OLD', 'ALIGNED', 200))
    _write(p, profit_rows); _write(m, micro_rows)
    out = ejc.audit(tmp_path)
    assert out['status'] == 'DESIGN_READ_AVAILABLE'
    assert out['matched_forward_ids'] == 40
    assert out['whole_history_overlap_status'] == 'COHORT_MISMATCH'
    assert out['aligned_cohort_status'] == 'ALIGNED_COHORT_COMPLETE'
    assert out['pre_alignment_rows_excluded_by_layer']['profit_engine'] == 1
    assert out['pre_alignment_rows_excluded_by_layer']['microstructure'] == 1


def test_missing_capture_inside_aligned_period_fails_closed(tmp_path):
    _populate_balanced(tmp_path, 40)
    vol_path = Path(tmp_path) / eeo.FILES['volatility']
    rows = [json.loads(x) for x in vol_path.read_text(encoding='utf-8').splitlines()]
    rows[-1]['forward_id'] = 'OTHER'
    _write(vol_path, rows)
    out = ejc.audit(tmp_path)
    assert out['status'] == 'COHORT_NOT_COMPARABLE'
    assert out['future_interaction_validation_supported'] is False
    assert out['horizon_coverage'] == {}
    assert 'ALIGNED_FROZEN_SIGNAL_COHORT_REQUIRED' in out['blockers']
    assert 'ALIGNED_FROZEN_SIGNAL_COHORT_INCOMPLETE' in out['blockers']


def test_missing_files_stays_collecting_and_never_claims_readiness(tmp_path):
    out = ejc.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['future_interaction_validation_supported'] is False
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False


def test_install_is_read_only_and_refreshes(tmp_path):
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(DATA=Path(tmp_path), production_decision=decision, forward_observe=forward)
    state = ejc.install(collector)
    assert collector.production_decision is decision
    assert collector.forward_observe is forward
    assert state['read_only'] is True
    assert state['wraps_production_decision'] is False
    assert state['wraps_forward_observe'] is False
    _populate_balanced(tmp_path, 40)
    refreshed = collector.edge_evidence_joint_coverage_refresh()
    assert refreshed['status'] == 'DESIGN_READ_AVAILABLE'
    assert collector.production_decision is decision
    assert collector.forward_observe is forward


def test_install_is_idempotent(tmp_path):
    collector = SimpleNamespace(DATA=Path(tmp_path), production_decision=lambda symbol: {'ok': True}, forward_observe=lambda payload: {'id': 'F1'})
    first = ejc.install(collector)
    second = ejc.install(collector)
    assert first is second
