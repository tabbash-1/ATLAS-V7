import copy

import historical_evaluation_protocol as p
import historical_microstructure_evaluator as e
import historical_replay_registry as r


def feature(i, relation='ALIGNED', direction='LONG'):
    return {
        'schema':'ATLAS_HISTORICAL_MICROSTRUCTURE_FEATURE_ROW_V1',
        'forward_id':f'f{i}','forward_captured_at_ms':i+1,'symbol':'BTCUSDT',
        'direction':direction,'entry':100.0,'score':70,'regime':'TREND_UP','rr_tp2':1.5,
        'microstructure_memory':{},'consensus':'BULLISH_FLOW','relation_to_signal':relation,
        'ready_windows':2,'source_smart_rows_prior_only':5,'outcome_known_to_builder':False,
        'retrospective_reconstruction':True,'forward_proof_equivalent':False,
        'research_only':True,'can_override_production':False,
    }


def states(rows):
    manifest={
        'schema':r.VERSION,'frozen_at':'x','research_only':True,'live_execution':False,
        'retrospective_reconstruction':True,'forward_proof_equivalent':False,
        'outcomes_read_before_freeze':False,'settlement_files_read_before_freeze':False,
        'future_data_allowed':False,'minimum_ready_rows':r.MIN_READY_ROWS,'feature_rows':len(rows),
        'source_feature_report_schema':'x','source_total_feature_rows':len(rows),
        'source_first_forward_ms':1,'source_last_forward_ms':len(rows),
        'feature_dataset_sha256':r._canonical_hash(rows),'rows':rows,
    }
    pm=p.build_manifest(manifest['feature_dataset_sha256'],'x')
    rs={'status':'FROZEN_READY','registration_locked':True,'feature_dataset_sha256':manifest['feature_dataset_sha256'],'manifest':manifest}
    ps={'status':'PREREGISTERED','registration_locked':True,'feature_dataset_sha256':manifest['feature_dataset_sha256'],'protocol_hash':pm['protocol_hash'],'manifest':pm}
    return rs,ps


def raw(rows, primary_exposed=0.5, primary_control=0.0, secondary_exposed=10.0, secondary_control=-10.0):
    out=[]
    for x in rows:
        exposed=x['relation_to_signal']=='ALIGNED'
        pr=primary_exposed if exposed else primary_control
        sr=secondary_exposed if exposed else secondary_control
        # Stored return is market return; invert for SHORT so directional result remains pr/sr.
        sign=1 if x['direction']=='LONG' else -1
        out.append({'id':x['forward_id'],'forward_return_pct':{'12':pr*sign,'24':sr*sign}})
    return out


def population():
    # 30 exposed + 30 control, chronologically interleaved so each fold has both.
    rows=[]
    for i in range(60):
        relation='ALIGNED' if i%2==0 else ('OPPOSED_OR_CROWDED' if i%4==1 else 'MIXED_OR_INSUFFICIENT')
        rows.append(feature(i,relation,'LONG' if i%3 else 'SHORT'))
    return rows


def test_invalid_hash_blocks_before_outcome_loader():
    rows=population(); rs,ps=states(rows)
    rs['feature_dataset_sha256']='tampered'
    calls={'n':0}
    def loader(): calls['n']+=1; return raw(rows)
    z=e.evaluate(rs,ps,loader)
    assert z['status']=='BLOCKED'
    assert z['outcome_loader_called'] is False
    assert calls['n']==0


def test_missing_primary_is_excluded_not_zero_filled():
    rows=population(); rs,ps=states(rows)
    rr=raw(rows,0.5,0.0)
    rr[0]['forward_return_pct']['12']=None
    z=e.evaluate(rs,ps,lambda:rr)
    assert z['missing_primary_rows']==1
    assert z['primary_matured_rows']==59
    assert z['primary']['exposed_aligned']['n']==29


def test_secondary_24h_cannot_rescue_primary_failure():
    rows=population(); rs,ps=states(rows)
    # 12h exposed underperforms, while 24h looks spectacular. Primary must fail.
    z=e.evaluate(rs,ps,lambda:raw(rows,-0.2,0.2,50.0,-50.0))
    assert z['primary_edge_claim'] is False
    assert z['secondary_descriptive_only']['used_for_edge_claim'] is False


def test_preregistered_thresholds_and_folds_can_support_edge():
    rows=population(); rs,ps=states(rows)
    z=e.evaluate(rs,ps,lambda:raw(rows,0.5,-0.1))
    assert z['primary']['mean_return_delta_pct_points'] >= 0.10
    assert z['primary']['positive_rate_delta_percentage_points'] >= 5.0
    assert z['primary']['positive_mean_delta_folds'] >= 2
    assert z['primary_edge_claim'] is True
    assert z['status']=='RETROSPECTIVE_EDGE_SUPPORTED'


def test_short_direction_is_inverted_correctly():
    rows=population(); rs,ps=states(rows)
    z=e.evaluate(rs,ps,lambda:raw(rows,0.5,-0.1))
    assert z['primary']['exposed_aligned']['mean_pct']==0.5
    assert z['primary']['control_predeclared']['mean_pct']==-0.1


if __name__=='__main__':
    test_invalid_hash_blocks_before_outcome_loader()
    test_missing_primary_is_excluded_not_zero_filled()
    test_secondary_24h_cannot_rescue_primary_failure()
    test_preregistered_thresholds_and_folds_can_support_edge()
    test_short_direction_is_inverted_correctly()
    print('historical microstructure evaluator tests: OK')
