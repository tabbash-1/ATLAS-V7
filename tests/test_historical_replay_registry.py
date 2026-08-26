import json
from pathlib import Path
from tempfile import TemporaryDirectory

import historical_replay_registry as reg


def feature(i):
    return {
        'schema':'ATLAS_HISTORICAL_MICROSTRUCTURE_FEATURE_ROW_V1',
        'forward_id':f'f{i}','forward_captured_at_ms':i+1,'symbol':'BTCUSDT',
        'direction':'LONG','entry':100.0,'score':70,'regime':'TREND_UP','rr_tp2':1.5,
        'microstructure_memory':{},'consensus':'MIXED','relation_to_signal':'MIXED_OR_INSUFFICIENT',
        'ready_windows':2,'source_smart_rows_prior_only':5,'outcome_known_to_builder':False,
        'retrospective_reconstruction':True,'forward_proof_equivalent':False,
        'research_only':True,'can_override_production':False,
    }


def manifest(n=60):
    rows=[feature(i) for i in range(n)]
    return {
        'schema':reg.VERSION,'frozen_at':'x','research_only':True,'live_execution':False,
        'retrospective_reconstruction':True,'forward_proof_equivalent':False,
        'outcomes_read_before_freeze':False,'settlement_files_read_before_freeze':False,
        'future_data_allowed':False,'minimum_ready_rows':reg.MIN_READY_ROWS,
        'feature_rows':len(rows),'source_feature_report_schema':'x',
        'source_total_feature_rows':len(rows),'source_first_forward_ms':1,
        'source_last_forward_ms':n,'feature_dataset_sha256':reg._canonical_hash(rows),'rows':rows,
    }


def test_valid_manifest_is_accepted():
    ok, err=reg.validate_manifest(manifest())
    assert ok is True and err is None


def test_hash_tamper_fails_closed():
    m=manifest(); m['rows'][0]['consensus']='BULLISH_FLOW'
    ok, err=reg.validate_manifest(m)
    assert ok is False and err=='FEATURE_HASH_MISMATCH'


def test_too_small_manifest_is_rejected():
    m=manifest(59)
    ok, err=reg.validate_manifest(m)
    assert ok is False and err=='FROZEN_SAMPLE_BELOW_MINIMUM'


def test_outcome_flag_violation_rejected():
    m=manifest(); m['rows'][0]['outcome_known_to_builder']=True
    m['feature_dataset_sha256']=reg._canonical_hash(m['rows'])
    ok, err=reg.validate_manifest(m)
    assert ok is False and err=='OUTCOME_FLAG_VIOLATION'


if __name__=='__main__':
    test_valid_manifest_is_accepted()
    test_hash_tamper_fails_closed()
    test_too_small_manifest_is_rejected()
    test_outcome_flag_violation_rejected()
    print('historical replay registry tests: OK')
