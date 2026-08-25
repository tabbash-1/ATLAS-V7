import json
from pathlib import Path
from types import SimpleNamespace

import edge_evidence_overlap as eeo


def row(schema, fid, *, qualified=True, research=False):
    return {
        'schema': schema,
        'forward_id': fid,
        'production_signal_qualified': qualified,
        'research_sample': research,
    }


def write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(json.dumps(x) if not isinstance(x, str) else x for x in rows) + '\n')


def populate(data_dir, profit_ids, micro_ids, vol_ids):
    write(Path(data_dir) / eeo.FILES['profit_engine'], [row(eeo.SCHEMAS['profit_engine'], x) for x in profit_ids])
    write(Path(data_dir) / eeo.FILES['microstructure'], [row(eeo.SCHEMAS['microstructure'], x) for x in micro_ids])
    write(Path(data_dir) / eeo.FILES['volatility'], [row(eeo.SCHEMAS['volatility'], x) for x in vol_ids])


def test_full_overlap_is_identical(tmp_path):
    ids = ['F1', 'F2', 'F3']
    populate(tmp_path, ids, ids, ids)
    out = eeo.audit(tmp_path)
    assert out['status'] == 'COHORTS_IDENTICAL'
    assert out['union_unique_forward_ids'] == 3
    assert out['three_way_intersection_unique_forward_ids'] == 3
    assert out['three_way_overlap_pct_of_union'] == 100.0
    assert out['blockers'] == []
    assert out['outcomes_read'] is False
    assert out['historical_features_recomputed'] is False
    assert out['gate_promoted'] is False


def test_partial_overlap_reports_exact_missing_ids(tmp_path):
    populate(tmp_path, ['F1', 'F2', 'F3'], ['F1', 'F2'], ['F1', 'F3'])
    out = eeo.audit(tmp_path)
    assert out['status'] == 'COHORT_MISMATCH'
    assert out['union_unique_forward_ids'] == 3
    assert out['three_way_intersection_unique_forward_ids'] == 1
    assert out['missing_forward_ids_by_layer']['profit_engine'] == []
    assert out['missing_forward_ids_by_layer']['microstructure'] == ['F3']
    assert out['missing_forward_ids_by_layer']['volatility'] == ['F2']
    assert 'FROZEN_SIGNAL_COHORTS_NOT_IDENTICAL' in out['blockers']


def test_duplicates_are_counted_and_block_identical_status(tmp_path):
    populate(tmp_path, ['F1', 'F1', 'F2'], ['F1', 'F2'], ['F1', 'F2'])
    out = eeo.audit(tmp_path)
    assert out['status'] == 'COHORT_MISMATCH'
    assert out['layers']['profit_engine']['duplicate_forward_id_rows'] == 1
    assert out['layers']['profit_engine']['unique_forward_ids'] == 2
    assert out['duplicate_layers'] == ['profit_engine']
    assert 'DUPLICATE_FORWARD_IDS_IN_FROZEN_EVIDENCE' in out['blockers']


def test_research_unqualified_wrong_schema_and_malformed_are_excluded(tmp_path):
    p = Path(tmp_path) / eeo.FILES['profit_engine']
    write(p, [
        row(eeo.SCHEMAS['profit_engine'], 'F1'),
        row(eeo.SCHEMAS['profit_engine'], 'R1', research=True),
        row(eeo.SCHEMAS['profit_engine'], 'U1', qualified=False),
        row('WRONG', 'W1'),
        '{broken json',
        row(eeo.SCHEMAS['profit_engine'], None),
    ])
    write(Path(tmp_path) / eeo.FILES['microstructure'], [row(eeo.SCHEMAS['microstructure'], 'F1')])
    write(Path(tmp_path) / eeo.FILES['volatility'], [row(eeo.SCHEMAS['volatility'], 'F1')])
    out = eeo.audit(tmp_path)
    stats = out['layers']['profit_engine']
    assert stats['valid_rows'] == 1
    assert stats['research_or_unqualified_rows_excluded'] == 2
    assert stats['wrong_schema_rows'] == 1
    assert stats['malformed_rows'] == 1
    assert stats['missing_forward_id_rows'] == 1
    assert out['status'] == 'COHORTS_IDENTICAL'


def test_missing_sidecar_is_explicit(tmp_path):
    write(Path(tmp_path) / eeo.FILES['profit_engine'], [row(eeo.SCHEMAS['profit_engine'], 'F1')])
    write(Path(tmp_path) / eeo.FILES['microstructure'], [row(eeo.SCHEMAS['microstructure'], 'F1')])
    out = eeo.audit(tmp_path)
    assert out['status'] == 'COHORT_MISMATCH'
    assert out['missing_files'] == ['volatility']
    assert 'FROZEN_EVIDENCE_SIDECAR_MISSING' in out['blockers']


def test_empty_universe_is_collecting_not_ready(tmp_path):
    out = eeo.audit(tmp_path)
    assert out['status'] == 'COLLECTING'
    assert out['union_unique_forward_ids'] == 0
    assert 'NO_FROZEN_SIGNAL_COHORT_AVAILABLE' in out['blockers']
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False


def test_install_is_read_only_and_refreshes(tmp_path):
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(DATA=Path(tmp_path), production_decision=decision, forward_observe=forward)
    state = eeo.install(collector)
    assert collector.production_decision is decision
    assert collector.forward_observe is forward
    assert state['read_only'] is True
    assert state['report']['status'] == 'COLLECTING'

    ids = ['F1']
    populate(tmp_path, ids, ids, ids)
    refreshed = collector.edge_evidence_overlap_refresh()
    assert refreshed['status'] == 'COHORTS_IDENTICAL'
    assert collector.production_decision is decision
    assert collector.forward_observe is forward


def test_install_is_idempotent(tmp_path):
    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=lambda symbol: {'ok': True},
        forward_observe=lambda payload: {'id': 'F1'},
    )
    first = eeo.install(collector)
    second = eeo.install(collector)
    assert first is second
