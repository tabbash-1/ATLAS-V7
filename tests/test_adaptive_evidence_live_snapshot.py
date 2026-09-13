import adaptive_evidence_live_snapshot as m


def _rows(n=20, start=0):
    out=[]
    for i in range(n):
        p=100+i*0.1
        out.append({'t':start+i*3600_000,'o':p,'h':p+1,'l':p-1,'c':p+0.2,'v':100+i})
    return out


def test_closed_candle_filter_excludes_open_bar():
    rows=_rows(3)
    got=m._closed(rows, now_ms=2*3600_000+30*60_000)
    assert len(got)==2
    assert got[-1]['t']==3600_000


def test_xrp_live_observation_calls_frozen_model():
    rows=_rows(20)
    old=m._factor_state
    try:
        m._factor_state=lambda rows,symbol:{
            'htf_4h':'LONG','htf_12h':'LONG','direction_1h':'LONG','direction':'LONG',
            'confirm_1h':True,'rsi':60.0,'rsi_aligned':True,
            'structure_break':True,'volume_confirmed':False,
        }
        obs=m.build_observation('XRPUSDT',rows,now_ms=30*3600_000)
    finally:
        m._factor_state=old
    assert obs['shadow_verdict']['decision']=='SHADOW_CANDIDATE'
    assert obs['shadow_verdict']['grade']=='A+'
    assert obs['research_only'] is True
    assert obs['live_execution'] is False
    assert obs['can_override_production'] is False
    assert obs['production_threshold_unchanged']==68
    assert obs['prospective_geometry']['horizon_h']==12
    assert obs['prospective_geometry']['modeled_round_trip_cost_bps']==10


def test_zec_requires_structure_and_volume():
    rows=_rows(20)
    old=m._factor_state
    try:
        m._factor_state=lambda rows,symbol:{
            'htf_4h':'SHORT','htf_12h':'SHORT','direction_1h':'SHORT','direction':'SHORT',
            'confirm_1h':True,'rsi':40.0,'rsi_aligned':True,
            'structure_break':False,'volume_confirmed':True,
        }
        obs=m.build_observation('ZECUSDT',rows,now_ms=30*3600_000)
    finally:
        m._factor_state=old
    assert obs['shadow_verdict']['decision']=='WAIT'
    assert 'WAIT_FOR_4H_STRUCTURE_BREAK' in obs['shadow_verdict']['reasons']
    assert obs['prospective_geometry'] is None


def test_observation_id_is_stable_for_same_closed_bar():
    rows=_rows(20)
    old=m._factor_state
    try:
        m._factor_state=lambda rows,symbol:{
            'htf_4h':'LONG','htf_12h':'LONG','direction_1h':'LONG','direction':'LONG',
            'confirm_1h':True,'rsi':60.0,'rsi_aligned':True,
            'structure_break':False,'volume_confirmed':False,
        }
        a=m.build_observation('XRPUSDT',rows,now_ms=30*3600_000)
        b=m.build_observation('XRPUSDT',rows,now_ms=30*3600_000)
    finally:
        m._factor_state=old
    assert a['observation_id']==b['observation_id']
