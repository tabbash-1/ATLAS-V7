import strategy_change_review_gate as g


def rows(n=30,champion=-.2,shadow=.2,changed=True):
    out=[]
    for i in range(n):
        out.append({"decision_id":str(i),"captured_at":f"2026-09-{18+i//24:02d}T{i%24:02d}:00:00+00:00",
                    "champion_net_r":champion,"shadow_net_r":shadow,
                    "policy_effect":"REPRICED_PATH" if changed else "UNCHANGED_CHAMPION_PATH"})
    return out


def test_gate_is_manual_only_and_prelocked():
    assert g.MIN_PAIRED_N==30 and g.MIN_EFFECT_N==10 and g.MIN_SEGMENT_N==10
    assert g.MIN_DELTA_AVG_R==.10 and g.MIN_SHADOW_PF==1.10
    assert g.THRESHOLD==68 and g.ACTIVATION_AT=="2026-09-18T07:10:00+00:00"


def test_insufficient_sample_cannot_pass():
    x=g._evaluate("X","FILTER",rows(29))
    assert x["passed"] is False
    assert x["decision"]=="INSUFFICIENT_PROSPECTIVE_SAMPLE"


def test_unaffected_policy_cannot_pass_even_with_good_shadow():
    x=g._evaluate("X","FILTER",rows(30,champion=.1,shadow=.2,changed=False))
    assert x["checks"]["affected_n"] is False
    assert x["passed"] is False


def test_robust_improvement_can_only_reach_manual_review():
    # Alternating small wins/losses preserves finite PF and positive expectancy.
    rr=[]
    for i in range(30):
        c=-.2 if i%2==0 else .05
        s=.25 if i%2==0 else -.05
        rr.append({"decision_id":str(i),"captured_at":f"2026-09-19T{i%24:02d}:{(i//24)*10:02d}:00+00:00",
                   "champion_net_r":c,"shadow_net_r":s,"policy_effect":"REPRICED_PATH"})
    x=g._evaluate("X","PATH_CHANGE",rr)
    assert x["passed"] is True
    assert x["decision"]=="ELIGIBLE_FOR_MANUAL_IMPLEMENTATION_REVIEW"
    assert x["automatic_promotion"] is False
    assert x["production_impact"]=="NONE"


def test_worse_drawdown_blocks_change():
    rr=rows(30,champion=.1,shadow=.2)
    # create a shadow loss streak while keeping average positive
    for i in range(10,15): rr[i]["shadow_net_r"]=-.5
    x=g._evaluate("X","FILTER",rr)
    assert x["checks"]["drawdown_not_worse"] is False
    assert x["passed"] is False


def test_metrics_are_chronological_and_no_best_variant_ranking_exists():
    x=g._evaluate("X","FILTER",rows(30))
    assert x["early_delta"]["n"]==15 and x["late_delta"]["n"]==15
    assert "rank" not in x and "score" not in x
