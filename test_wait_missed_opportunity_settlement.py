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
    row={'id':'a','decision_id':'a','symbol':'BTCUSDT','captured_at':start,'captured_at_ms':int(start.timestamp()*1000),'direction':'LONG','price':100.0,'invalidation':98.0,'score':68.0,'threshold':68.0,'reason':'WAIT','raw_reason':'WAIT','blocker_family':'HTF_CONFLICT','playbook':'X','release':None,'v2_regime':None,'epoch_id':'LEGACY_BASELINE'}
    out=m.settle(row,start+dt.timedelta(hours=13))
    assert out['horizons']['12h']['directional_return_pct'] > 0
    assert out['missed_opportunity'] is True
    row['direction']='SHORT'; row['invalidation']=103.0
    out2=m.settle(row,start+dt.timedelta(hours=13))
    assert out2['horizons']['12h']['directional_return_pct'] < 0


def test_epoch_boundary_is_explicit_and_immutable():
    assert m.POST_V2_START == dt.datetime(2026,9,14,12,31,29,tzinfo=dt.timezone.utc)
    assert m.POST_V2_RELEASE_SHA == '0e3db49b3511f845e4df52db49d41700d14a4eee'
    assert m.POST_V2_EPOCH_ID == 'HTF_SR_V2_2026-09-14'


def test_cohort_summary_never_mixes_legacy_and_post_v2():
    def r(epoch, missed, regime=None):
        return {'epoch_id':epoch,'missed_opportunity':missed,'blocker_family':'HTF_CONFLICT','v2_regime':regime,'horizons':{'4h':{'directional_return_pct':1.0},'8h':{'directional_return_pct':1.0},'12h':{'directional_return_pct':1.0}}}
    rows=[r('LEGACY_BASELINE',True),r(m.POST_V2_EPOCH_ID,False),r(m.POST_V2_EPOCH_ID,True,'4H_DIRECTIONAL_12H_NEUTRAL')]
    c=m.cohort_summary(rows)
    assert c['legacy_baseline']['matured_classified']==1
    assert c['post_v2_forward']['matured_classified']==2
    assert c['post_v2_neutral_regime']['matured_classified']==1
    assert c['post_v2_forward']['missed_n']==1


def test_research_only_contract():
    assert m.SCHEMA == 'ATLAS_WAIT_MISSED_OPPORTUNITY_V2_CANDLE_SETTLED'
    assert m.HORIZONS == (1,2,4,8,12)
