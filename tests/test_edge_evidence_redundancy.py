import json
from pathlib import Path
from types import SimpleNamespace

import edge_evidence_overlap as eeo
import edge_evidence_redundancy as eer


def _write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(x) for x in rows) + '\n', encoding='utf-8')


def _profit(fid, reason):
    return {
        'schema': eeo.SCHEMAS['profit_engine'],
        'forward_id': fid,
        'production_signal_qualified': True,
        'research_sample': False,
        'profit_engine': {'regime_gate': {'reason': reason}},
        # Shared Production fields must be ignored by the redundancy audit.
        'direction': 'LONG', 'entry': 100, 'score': 70,
    }


def _micro(fid, relation):
    return {
        'schema': eeo.SCHEMAS['microstructure'],
        'forward_id': fid,
        'production_signal_qualified': True,
        'research_sample': False,
        'relation_to_signal': relation,
        'direction': 'LONG', 'entry': 100, 'score': 70,
    }


def _vol(fid, label_by_h=None):
    label_by_h = label_by_h or {}
    fits = {}
    for h in eer.VOLATILITY_HORIZONS_H:
        label = label_by_h.get(h)
        if label is None:
            fits[str(h)] = {'status': 'INSUFFICIENT'}
        else:
            target, stop = label
            fits[str(h)] = {
                'status': 'READY',
                'target_fit': target,
                'stop_fit': stop,
            }
    return {
        'schema': eeo.SCHEMAS['volatility'],
        'forward_id': fid,
        'production_signal_qualified': True,
        'research_sample': False,
        'geometry_fit_by_horizon': fits,
        'direction': 'LONG', 'entry': 100, 'score': 70,
    }


def _populate(data_dir, n=20, mismatch=False, constant=False):
    profits = []
    micros = []
    vols = []
    for i in range(n):
        fid = f'F{i:03d}'
        if constant:
            p = 'REGIME_ALIGNED'
            m = 'ALIGNED'
        else:
            p = 'REGIME_ALIGNED' if i % 2 == 0 else 'ASSET_REGIME_NOT_ALIGNED'
            m = 'ALIGNED' if i % 2 == 0 else 'OPPOSED_OR_CROWDED'
        profits.append(_profit(fid, p))
        micros.append(_micro(fid, m))
        vols.append(_vol(fid, {
            1: ('PLAUSIBLE', 'PLAUSIBLE') if i % 2 == 0 else ('STRETCHED', 'TIGHT'),
            4: ('PLAUSIBLE', 'PLAUSIBLE') if i % 3 else ('CLOSE', 'WIDE'),
            12: ('CLOSE', 'PLAUSIBLE') if i % 2 == 0 else ('PLAUSIBLE', 'WIDE'),
        }))
    if mismatch and vols:
        vols[-1]['forward_id'] = 'OTHER'
    _write(Path(data_dir) / eeo.FILES['profit_engine'], profits)
    _write(Path(data_dir) / eeo.FILES['microstructure'], micros)
    _write(Path(data_dir) / eeo.FILES['volatility'], vols)


def test_identical_cohort_with_enough_rows_produces_descriptive_read(tmp_path):
    _populate(tmp_path, n=20)
    out = eer.audit(tmp_path)
    assert out['status'] == 'DESCRIPTIVE_READ_AVAILABLE'
    assert out['cohort_comparable'] is True
    assert out['matched_forward_ids'] == 20
    assert out['outcomes_read'] is False
    assert out['chosen_trade_horizon_assumed'] is False
    assert out['shared_production_fields_excluded'] == ['direction', 'entry', 'score', 'signal_threshold']
    assert out['associations']['profit_vs_microstructure']['cramers_v'] == 1.0
    assert out['associations']['profit_vs_microstructure']['observed_association_strength'] == 'HIGH_OBSERVED_ASSOCIATION'
    assert out['high_association_is_redundancy_proof'] is False
    assert out['low_association_is_independence_proof'] is False
    assert out['statistical_independence_claimed'] is False
    assert out['gate_promoted'] is False


def test_too_few_matched_rows_stays_collecting(tmp_path):
    _populate(tmp_path, n=8)
    out = eer.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['matched_forward_ids'] == 8
    assert 'INSUFFICIENT_MATCHED_FROZEN_OBSERVATIONS' in out['blockers']
    assert out['can_override_production'] is False


def test_cohort_mismatch_fails_closed_before_association_interpretation(tmp_path):
    _populate(tmp_path, n=20, mismatch=True)
    out = eer.audit(tmp_path)
    assert out['status'] == 'COHORT_NOT_COMPARABLE'
    assert out['cohort_comparable'] is False
    assert out['associations'] == {}
    assert 'IDENTICAL_FROZEN_SIGNAL_COHORT_REQUIRED' in out['blockers']


def test_constant_layer_output_marks_association_undefined(tmp_path):
    _populate(tmp_path, n=20, constant=True)
    out = eer.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['associations']['profit_vs_microstructure']['cramers_v'] is None
    assert out['associations']['profit_vs_microstructure']['observed_association_strength'] == 'UNDEFINED'
    assert 'ASSOCIATION_UNDEFINED_FOR_ONE_OR_MORE_PAIRS' in out['blockers']


def test_missing_files_is_collecting_and_never_ready(tmp_path):
    out = eer.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['cohort_comparable'] is False
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False


def test_install_is_read_only_and_refreshes(tmp_path):
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(DATA=Path(tmp_path), production_decision=decision, forward_observe=forward)
    state = eer.install(collector)
    assert collector.production_decision is decision
    assert collector.forward_observe is forward
    assert state['read_only'] is True
    assert state['wraps_production_decision'] is False
    assert state['wraps_forward_observe'] is False

    _populate(tmp_path, n=20)
    refreshed = collector.edge_evidence_redundancy_refresh()
    assert refreshed['status'] == 'DESCRIPTIVE_READ_AVAILABLE'
    assert collector.production_decision is decision
    assert collector.forward_observe is forward


def test_install_is_idempotent(tmp_path):
    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=lambda symbol: {'ok': True},
        forward_observe=lambda payload: {'id': 'F1'},
    )
    first = eer.install(collector)
    second = eer.install(collector)
    assert first is second
