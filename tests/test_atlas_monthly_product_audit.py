import datetime as dt
from atlas_monthly_product_audit import build, joint_setup_breakdown, nonoverlap


def snap(t, px, qualified=True, wait_reason=None):
    return (t, {'captured_at':t.isoformat(),'decisions':{'BTCUSDT':{'ok':True,'entry':px,'candidate_direction':'LONG','signal_qualified':qualified,'execution_ready':False,'score':72 if qualified else 64,'playbook':'MARKET_CONTINUATION_LONG','regime':'TREND_UP','wait_reason':wait_reason}}})


def test_monthly_audit_is_analyst_only_and_4_12h():
    t=dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)
    rows=[snap(t,100),snap(t+dt.timedelta(hours=4),102),snap(t+dt.timedelta(hours=8),103),snap(t+dt.timedelta(hours=12),104)]
    r=build(rows)
    assert r['ok'] is True
    assert r['product_contract']['canonical_horizon']=='4-12H'
    assert r['product_contract']['analyst_only'] is True
    assert r['product_contract']['live_execution'] is False
    assert r['can_override_production'] is False
    assert r['production_threshold_changed'] is False
    assert set(r['qualified'])=={'4','8','12'}


def test_wait_missed_opportunity_is_attributed_not_promoted():
    t=dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)
    rows=[snap(t,100,False,'SCORE_BELOW_SIGNAL_THRESHOLD'),snap(t+dt.timedelta(hours=4),101,False,'SCORE_BELOW_SIGNAL_THRESHOLD'),snap(t+dt.timedelta(hours=8),102,False,'SCORE_BELOW_SIGNAL_THRESHOLD'),snap(t+dt.timedelta(hours=12),103,False,'SCORE_BELOW_SIGNAL_THRESHOLD')]
    r=build(rows)
    assert r['counts']['qualified']==0
    assert r['missed_wait_opportunities_12h_ge_1pct_by_reason']['SCORE_BELOW_SIGNAL_THRESHOLD']>=1
    assert r['production_threshold_changed'] is False


def test_joint_setup_breakdown_keeps_quarantine_dimensions_together():
    items=[{"direction":"LONG","regime":"TREND_UP","playbook":"TREND_PULLBACK_LONG","horizons":{"4":{"directional_return_pct":1},"8":{"directional_return_pct":2},"12":{"directional_return_pct":3}}}]
    out=joint_setup_breakdown(items)
    assert out["LONG|TREND_UP|TREND_PULLBACK_LONG"]["12"]["n"]==1
    assert out["LONG|TREND_UP|TREND_PULLBACK_LONG"]["12"]["mean_pct"]==3.0


def test_nonoverlap_reduces_same_setup_12h_dependence():
    base=dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)
    items=[]
    for h in (0,1,13):
        items.append({"captured_at":(base+dt.timedelta(hours=h)).isoformat(),"symbol":"BTCUSDT","direction":"LONG","regime":"TREND_UP","playbook":"TREND_PULLBACK_LONG","horizons":{}})
    out=nonoverlap(items,12)
    assert len(out)==2
