import entry_provenance_cohort_evidence as m


def base_row(i=1, net=.5, direction="LONG", score=75, feature=None):
    p={"schema":m.PROVENANCE_SCHEMA,"frozen_before_outcome":True,"score":score,"threshold":68,
       "htf_alignment_class":"ALIGNED","htf_regime":"4H_DIRECTIONAL_12H_NEUTRAL",
       "breakout_confirmed":True,"continuation_strong":True,"futures_alignment":"ALIGNED",
       "entry_mode":"NOW","scenario_readiness":"READY","setup_quality_status":"PASS",
       "playbook":"TREND_PULLBACK_LONG","market_regime":"TREND_UP"}
    if feature: p.update(feature)
    return {"decision_id":f"d{i}","symbol":"BTCUSDT","direction":direction,
            "captured_at":"2026-09-18T00:00:00Z","decision_provenance":p,
            "settlement":{"terminal":True,"r_multiple":net+.1}}


def cost_map(rows):
    return {r["decision_id"]:{"decision_id":r["decision_id"],"net_r":float(r["settlement"]["r_multiple"])-.1} for r in rows}


def test_requires_frozen_provenance():
    r=base_row(); r["decision_provenance"]["frozen_before_outcome"]=False
    assert m._feature_row(r,cost_map([r])) is None


def test_requires_cost_adjusted_settlement():
    r=base_row()
    assert m._feature_row(r,{}) is None


def test_feature_row_uses_frozen_preoutcome_fields():
    r=base_row(score=68,feature={"futures_alignment":"OPPOSED","breakout_confirmed":False})
    z=m._feature_row(r,cost_map([r]))
    assert z["score_margin_bucket"]=="MARGIN_LE_0"
    assert z["futures_alignment"]=="OPPOSED"
    assert z["breakout_confirmed"]=="False"


def test_score_margin_buckets_locked():
    assert m._score_bucket(68,68)=="MARGIN_LE_0"
    assert m._score_bucket(72,68)=="MARGIN_0_TO_5"
    assert m._score_bucket(80,68)=="MARGIN_5_TO_15"
    assert m._score_bucket(90,68)=="MARGIN_GT_15"


def test_no_hypothesis_before_formal_total():
    rows=[]
    for i in range(20):
        raw=base_row(i,net=(-.5 if i<10 else .5),feature={"futures_alignment":"OPPOSED" if i<10 else "ALIGNED"})
        rows.append(m._feature_row(raw,cost_map([raw])))
    assert m._hypotheses(rows,m._cohorts(rows))==[]


def test_prelocked_negative_feature_can_only_nominate_shadow_test():
    rows=[]
    for i in range(30):
        bad=i<15
        raw=base_row(i,net=(-.6 if bad else .4),feature={"futures_alignment":"OPPOSED" if bad else "ALIGNED"})
        rows.append(m._feature_row(raw,cost_map([raw])))
    hs=m._hypotheses(rows,m._cohorts(rows))
    h=next(x for x in hs if x["dimension"]=="futures_alignment" and x["value"]=="OPPOSED")
    assert h["kind"]=="NEGATIVE_FEATURE_SHADOW_FILTER_CANDIDATE"
    assert h["action"]=="SHADOW_TEST_ONLY"
    assert h["bucket"]["n"]==15 and h["complement"]["n"]==15


def test_safety_constants_are_locked():
    assert m.THRESHOLD==68
    assert m.MIN_TOTAL_PROVENANCE==30
    assert m.MIN_BUCKET_N==10
    assert m.MIN_COMPLEMENT_N==10
    assert m.MIN_ABS_DELTA_R==.25
