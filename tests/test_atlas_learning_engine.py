#!/usr/bin/env python3
import json, pathlib, tempfile
import atlas_learning_engine as l


def test_safety_contract():
    r=l.build()
    assert r['schema']=='ATLAS_LEARNING_ENGINE_V1'
    assert r['canonical_contract']=='analyst_output'
    assert r['product_horizon']=='4-12H'
    s=r['safety']
    assert s['research_only'] is True
    assert s['paper_only'] is True
    assert s['analysis_only'] is True
    assert s['live_execution'] is False
    assert s['can_override_production'] is False
    assert s['can_change_score'] is False
    assert s['can_change_threshold'] is False
    assert s['can_change_geometry'] is False
    assert s['can_change_decision'] is False
    assert r['methodology']['future_leakage_allowed'] is False
    assert r['methodology']['automatic_learning_updates'] is False
    assert r['proof_status']['edge_proven'] is False
    assert r['next_actions']['auto_promote'] is False


def test_wait_mapping_never_uses_earlier_checkpoint():
    assert l._wait_horizon(4)==6
    assert l._wait_horizon(8)==12
    assert l._wait_horizon(12)==12


def test_blocker_small_sample_cannot_authorize_change():
    payload={'records':[{
        'candidate_direction':'LONG','reason':'SCORE_BELOW_SIGNAL_THRESHOLD','score':67,'threshold':68,
        'horizons':{'12h':{'directional_return_pct':2.0,'change_pct':2.0}},
        'score_attribution':{}
    }]}
    rows=l._blocker_attribution(payload)
    assert rows
    assert rows[0]['verdict']=='INSUFFICIENT_SAMPLE'
    assert rows[0]['production_change_authorized'] is False


def test_output_is_serializable():
    json.dumps(l.build())


if __name__=='__main__':
    test_safety_contract()
    test_wait_mapping_never_uses_earlier_checkpoint()
    test_blocker_small_sample_cannot_authorize_change()
    test_output_is_serializable()
    print('PASS atlas learning engine')
