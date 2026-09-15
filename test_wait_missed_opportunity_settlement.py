import datetime as dt
import wait_missed_opportunity_settlement as m


def base_decision():
    return {
        'ok': True,
        'candidate_direction': 'LONG',
        'indicators': {'price': 100.0},
        'trade_plan': {'entry': 105.0, 'stop_loss': 98.0},
        'canonical_decision': {'schema':'ATLAS_CANONICAL_DECISION_TRUTH_V1','canonical_source_present':True,'source_of_truth':'FINAL_TRADE_GATE','trade_ready':False,'decision_id':'x','score':68,'threshold':68,'wait_reason':'HTF_CONFLICT'},
        'htf_sr_decision_v2': {'regime':'4H_DIRECTIONAL_12H_NEUTRAL','blockers':['HTF_4H_12H_NOT_ALIGNED'],'primary_blocker':'HTF_4H_12H_NOT_ALIGNED'}
    }


def test_observed_price_never_uses_trigger_entry():
    assert m.observed_price(base_decision()) == 100.0


def test_invalidation_must_be_correct_side():
    d=base_decision(); assert m.invalidation_price(d,'LONG') == 98.0
    d['trade_plan']['stop_loss']=101.0; assert m.invalidation_price(d,'LONG') is None


def test_blocker_family_htf():
    d=base_decision(); t=d['canonical_decision']; assert m.blocker_family(d,t) == 'HTF_CONFLICT'


def test_settlement_direction_symmetry(monkeypatch):
    start=dt.datetime(2026,1,1,tzinfo=dt.timezone.utc)
    candles=[]
    for i in range(144):
        p=100.0 + i/143*2.0
        candles.append({'open_time':int(start.timestamp()*1000)+i*5*60_000,'open':p,'high':p+0.05,'low':p-0.05,'close':p})
    monkeypatch.setattr(m,'market_klines',lambda *a,**k:(candles,'TEST'))
    row={'id':'a','decision_id':'a','symbol':'BTCUSDT','captured_at':start,'captured_at_ms':int(start.timestamp()*1000),'direction':'LONG','price':100.0,'invalidation':98.0,'score':68.0,'threshold':68.0,'reason':'WAIT','raw_reason':'WAIT','blocker_family':'HTF_CONFLICT','playbook':'X','release':None,'v2_regime':None}
    out=m.settle(row,start+dt.timedelta(hours=13))
    assert out['horizons']['12h']['directional_return_pct'] > 0
    assert out['missed_opportunity'] is True
    row['direction']='SHORT'; row['invalidation']=103.0
    out2=m.settle(row,start+dt.timedelta(hours=13))
    assert out2['horizons']['12h']['directional_return_pct'] < 0


def test_research_only_contract():
    assert m.SCHEMA == 'ATLAS_WAIT_MISSED_OPPORTUNITY_V2_CANDLE_SETTLED'
    assert m.HORIZONS == (1,2,4,8,12)
