import datetime as dt

import paper_portfolio_10k as p


def manifest():
    return {
        'portfolio_id':'ATLAS_10K_PAPER_V1','cohort_start_at':'2026-09-02T11:52:00+00:00','starting_equity_usd':10000.0,
        'risk_per_trade_pct':1.0,'max_concurrent_positions':3,'holding_horizon_hours':12,'production_threshold':68,
        'manifest_hash':'x'
    }


def ready(direction='LONG', entry=100.0, stop=99.0, tp2=102.0):
    tp1=101.0 if direction=='LONG' else 99.0
    if direction=='SHORT': stop=101.0; tp2=98.0
    return {'execution_ready':True,'actionable_decision':direction,'candidate_direction':direction,'score':75,'signal_threshold':68,
            'trade_plan':{'can_execute':True,'direction':direction,'entry':entry,'stop_loss':stop,'tp1':tp1,'tp2':tp2,'rr_tp2':2.0}}


def test_trade_ready_requires_explicit_permission_and_action():
    d=ready(); assert p.trade_ready(d)
    d2=ready(); d2['trade_plan']['can_execute']=False; assert not p.trade_ready(d2)
    d3=ready(); d3['execution_ready']=False; assert not p.trade_ready(d3)
    d4=ready(); d4['actionable_decision']='WAIT'; assert not p.trade_ready(d4)


def test_geometry_rejects_invalid_long_ordering():
    d=ready(); d['trade_plan']['stop_loss']=101.0
    assert p.geometry(d) is None


def test_enrollment_is_prospective_transition_only_and_risk_frozen():
    m=manifest(); t0=dt.datetime.fromisoformat(m['cohort_start_at'])
    snaps=[
        (t0,{'decisions':{'BTCUSDT':ready()}}),
        (t0+dt.timedelta(minutes=20),{'decisions':{'BTCUSDT':ready()}}),
    ]
    cohort=[]
    added,newest=p.enroll_new(m,cohort,snaps,t0-dt.timedelta(microseconds=1),10000.0)
    assert len(added)==1 and len(cohort)==1
    assert cohort[0]['risk_usd']==100.0
    assert cohort[0]['outcome_known_at_entry'] is False
    assert newest==t0+dt.timedelta(minutes=20)


def test_concurrent_cap_blocks_fourth_trade():
    m=manifest(); t0=dt.datetime.fromisoformat(m['cohort_start_at'])
    decisions={s:ready() for s in ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT']}
    cohort=[]
    added,_=p.enroll_new(m,cohort,[(t0,{'decisions':decisions})],t0-dt.timedelta(microseconds=1),10000.0)
    assert len(added)==3


def test_append_only_integrity_detects_mutation():
    rows=[{'id':'a','v':1}]
    old={'row_hashes':p.verify_append_only(rows,None)}
    try:
        p.verify_append_only([{'id':'a','v':2}],old)
    except RuntimeError as e:
        assert 'APPEND_ONLY' in str(e)
    else:
        raise AssertionError('mutation was not detected')


def test_portfolio_report_computes_dollars_equity_drawdown_and_win_rate():
    m=manifest(); t0=dt.datetime.fromisoformat(m['cohort_start_at'])
    cohort=[
        {'id':'a','captured_at':t0.isoformat(),'captured_at_ms':int(t0.timestamp()*1000),'direction':'LONG','risk_usd':100.0},
        {'id':'b','captured_at':(t0+dt.timedelta(hours=1)).isoformat(),'captured_at_ms':int((t0+dt.timedelta(hours=1)).timestamp()*1000),'direction':'SHORT','risk_usd':100.0},
    ]
    settlements=[
        {'id':'a','terminal':True,'r_multiple':2.0,'exit_at_ms':int((t0+dt.timedelta(hours=2)).timestamp()*1000),'status':'WIN_TP2'},
        {'id':'b','terminal':True,'r_multiple':-1.0,'exit_at_ms':int((t0+dt.timedelta(hours=3)).timestamp()*1000),'status':'LOSS'},
    ]
    r=p.portfolio_report(m,cohort,settlements,t0.isoformat(),t0)
    pf=r['portfolio']
    assert pf['equity_usd']==10100.0
    assert pf['net_pnl_usd']==100.0
    assert pf['win_rate_pct']==50.0
    assert pf['max_drawdown_pct']>0
    assert pf['long']['pnl_usd']==200.0 and pf['short']['pnl_usd']==-100.0


if __name__=='__main__':
    tests=[globals()[n] for n in sorted(globals()) if n.startswith('test_') and callable(globals()[n])]
    for fn in tests: fn()
    print(f'paper portfolio tests: {len(tests)} ok')
