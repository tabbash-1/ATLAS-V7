import datetime as dt
from atlas_monthly_product_audit import build


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
