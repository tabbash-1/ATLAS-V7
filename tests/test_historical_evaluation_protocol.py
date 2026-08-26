from pathlib import Path
from tempfile import TemporaryDirectory

import historical_evaluation_protocol as p


class C:
    DATA = Path('.')
    HISTORICAL_REPLAY_REGISTRY_STATE = {
        'status':'FROZEN_READY', 'registration_locked':True,
        'feature_dataset_sha256':'abc123',
    }
    def now_iso(self): return '2026-08-26T00:00:00+00:00'


def test_manifest_tied_to_feature_hash_and_rules():
    m=p.build_manifest('abc123','x')
    ok,err=p.validate_manifest(m,'abc123')
    assert ok is True and err is None
    assert m['rules']['primary_horizon_hours']==12
    assert m['rules']['selection_policy']=='NO_GRID_SEARCH_NO_BEST_HORIZON_NO_POST_OUTCOME_RULE_CHANGES'


def test_feature_hash_mismatch_fails_closed():
    m=p.build_manifest('abc123','x')
    ok,err=p.validate_manifest(m,'different')
    assert ok is False and err=='FEATURE_HASH_MISMATCH'


def test_rule_tamper_fails_hash_or_rules():
    m=p.build_manifest('abc123','x')
    m['rules']['primary_horizon_hours']=1
    ok,err=p.validate_manifest(m,'abc123')
    assert ok is False and err in ('PROTOCOL_HASH_MISMATCH','RULES_MISMATCH')


def test_registration_is_persistent_and_not_rewritten():
    c=C()
    with TemporaryDirectory() as d:
        path=Path(d)/'protocol.json'
        a=p.refresh(c,path)
        assert a['status']=='PREREGISTERED'
        first=path.read_text()
        b=p.refresh(c,path)
        assert b['status']=='PREREGISTERED'
        assert path.read_text()==first


def test_no_registration_before_feature_freeze():
    class U(C):
        HISTORICAL_REPLAY_REGISTRY_STATE={'status':'COLLECTING_FEATURES','registration_locked':False,'feature_dataset_sha256':'x'}
    with TemporaryDirectory() as d:
        path=Path(d)/'protocol.json'
        s=p.refresh(U(),path)
        assert s['status']=='BLOCKED_FEATURE_DATASET_NOT_FROZEN'
        assert not path.exists()


if __name__=='__main__':
    test_manifest_tied_to_feature_hash_and_rules()
    test_feature_hash_mismatch_fails_closed()
    test_rule_tamper_fails_hash_or_rules()
    test_registration_is_persistent_and_not_rewritten()
    test_no_registration_before_feature_freeze()
    print('historical evaluation protocol tests: OK')
