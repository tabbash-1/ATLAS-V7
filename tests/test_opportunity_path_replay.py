import opportunity_path_replay as m


def candles(hours=3,start=0,base=100.0,step=.1):
    out=[]
    px=base
    for i in range(hours*12):
        t=start+i*300_000
        o=px;c=px+step;hi=max(o,c)+.05;lo=min(o,c)-.05
        out.append({"open_time":t,"open":o,"high":hi,"low":lo,"close":c})
        px=c
    return out


def row(direction="LONG"):
    return {"decision_id":"d1","captured_at_ms":0,"direction":direction,"paper_quantity":10.0,"risk_usd":10.0,
            "geometry":{"direction":direction,"entry":100.0,"stop_loss":99.0 if direction=="LONG" else 101.0,
                        "tp1":101.0 if direction=="LONG" else 99.0,"tp2":102.0 if direction=="LONG" else 98.0,
                        "risk_abs":1.0}}


def test_next_full_hour_never_uses_predecision_partial_hour():
    assert m._next_full_hour_ms(1)==3_600_000
    assert m._next_full_hour_ms(3_600_000)==3_600_000


def test_full_hour_requires_all_12_five_minute_bars():
    cs=candles(2)
    assert len(m._full_hour_bars(cs,0,2*3_600_000))==2
    assert len(m._full_hour_bars(cs[:-1],0,2*3_600_000))==1


def test_delay_entry_requires_directional_confirmation():
    cs=candles(3,step=-.01)
    z=m.replay_delay(row("LONG"),cs)
    assert z["state"]=="SHADOW_SKIP_NO_1H_CONFIRM"


def test_delay_entry_uses_original_quantity_not_resized_risk():
    cs=candles(3,step=.01)
    # keep TP2 far enough to avoid invalid delayed geometry
    r=row("LONG");r["geometry"]["tp1"]=102;r["geometry"]["tp2"]=103
    z=m.replay_delay(r,cs)
    assert z["state"]=="SETTLED"
    assert z["same_quantity_as_champion"] is True
    assert z["entry_at_ms"]==3_600_000


def test_failfast_exits_on_prelocked_adverse_one_hour_close():
    cs=candles(4,step=-.15)
    r=row("LONG");r["geometry"]["stop_loss"]=95;r["geometry"]["risk_abs"]=5;r["geometry"]["tp1"]=105;r["geometry"]["tp2"]=110
    z=m.replay_failfast(r,cs)
    assert z["state"]=="SETTLED"
    assert z["terminal"]=="FAILFAST_EXIT"
    assert z["adverse_trigger_r"]==-.25


def test_failfast_does_not_override_tp1_first():
    cs=candles(4,step=.1)
    r=row("LONG")
    z=m.replay_failfast(r,cs)
    assert z["state"]=="NO_FAILFAST_TRIGGER"


def test_cost_model_matches_locked_phase4_assumptions_at_12h():
    assert round(m._cost_usd(10000,12),2)==17.00


def _cohort_row(decision_id, geometry="G6", plan="V11", gate="V15"):
    return {"decision_id":decision_id,
            "geometry":{"geometry_version":geometry,"plan_version":plan},
            "decision_provenance":{"geometry_version":geometry,"trade_plan_version":plan,
                                   "final_trade_gate_version":gate}}


def test_version_cohort_separates_plan_and_gate_generations():
    a=m._version_cohort(_cohort_row("a",plan="V10",gate="V14"))
    b=m._version_cohort(_cohort_row("b",plan="V11",gate="V15"))
    assert a["fully_versioned"] and b["fully_versioned"]
    assert a["key"]!=b["key"]


def test_missing_version_provenance_never_pools():
    a=m._version_cohort({"decision_id":"a","geometry":{},"decision_provenance":{}})
    b=m._version_cohort({"decision_id":"b","geometry":{},"decision_provenance":{}})
    assert not a["fully_versioned"] and not b["fully_versioned"]
    assert a["key"]!=b["key"]


def test_thirty_rows_from_mixed_generations_do_not_unlock_formal_sample():
    paired=[]
    for i in range(15):
        c=m._version_cohort(_cohort_row(f"a{i}",plan="V10",gate="V14"))
        paired.append({"version_cohort":c,"champion_net_r":-1.0,"shadow_net_r":0.0})
    for i in range(15):
        c=m._version_cohort(_cohort_row(f"b{i}",plan="V11",gate="V15"))
        paired.append({"version_cohort":c,"champion_net_r":-1.0,"shadow_net_r":0.0})
    cohorts=m._summarize_version_cohorts(paired)
    assert sum(x["paired_n"] for x in cohorts)==30
    assert len(cohorts)==2
    assert not any(x["formal_ready"] for x in cohorts)


def test_thirty_rows_from_one_fully_versioned_generation_unlock_formal_sample():
    paired=[]
    for i in range(30):
        c=m._version_cohort(_cohort_row(f"a{i}"))
        paired.append({"version_cohort":c,"champion_net_r":-1.0,"shadow_net_r":0.0})
    cohorts=m._summarize_version_cohorts(paired)
    assert len(cohorts)==1 and cohorts[0]["formal_ready"] is True


def test_safety_constants_are_locked():
    assert m.ACTIVATION_AT=="2026-09-18T07:10:00+00:00"
    assert m.THRESHOLD==68 and m.MIN_N==30
    assert m.SOURCE_SCHEMA=="ATLAS_PRODUCTION_VALIDATION_SCORECARD_V2_DIAGNOSTICS"
    assert m.FAILFAST_ADVERSE_R==-.25 and m.FAILFAST_WINDOW_H==4
    assert {x["id"] for x in m.PATH_HYPOTHESES}=={"DELAY_ENTRY_1H_CONFIRM","EARLY_MOMENTUM_FAILFAST_EXIT","PROFIT_PROTECTION_TIME_DECAY"}


def test_delay_skip_is_paired_as_zero_r_not_dropped():
    v,e=m.shadow_pair_value("DELAY_ENTRY_1H_CONFIRM",{"state":"SHADOW_SKIP_NO_1H_CONFIRM"},-1.2)
    assert v==0.0 and e=="SKIPPED_BY_SHADOW_POLICY"


def test_failfast_no_trigger_is_paired_as_unchanged_champion():
    v,e=m.shadow_pair_value("EARLY_MOMENTUM_FAILFAST_EXIT",{"state":"NO_FAILFAST_TRIGGER"},0.7)
    assert v==0.7 and e=="UNCHANGED_CHAMPION_PATH"


def test_unavailable_path_remains_unpaired_fail_closed():
    v,e=m.shadow_pair_value("DELAY_ENTRY_1H_CONFIRM",{"state":"MARKET_DATA_INCOMPLETE"},-1)
    assert v is None and e is None


def test_profit_protection_constants_are_locked():
    assert m.PROTECT_CHECKPOINT_H==8
    assert m.PROTECT_MIN_FAVORABLE_R==0.15
    assert "PROFIT_PROTECTION_TIME_DECAY" in {x["id"] for x in m.PATH_HYPOTHESES}


def test_profit_protection_no_trigger_pairs_as_unchanged():
    v,e=m.shadow_pair_value("PROFIT_PROTECTION_TIME_DECAY",{"state":"NO_PROTECTION_TRIGGER"},0.4)
    assert v==0.4 and e=="UNCHANGED_CHAMPION_PATH"
