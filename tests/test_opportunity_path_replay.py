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


def test_safety_constants_are_locked():
    assert m.ACTIVATION_AT=="2026-09-18T07:10:00+00:00"
    assert m.THRESHOLD==68 and m.MIN_N==30
    assert m.FAILFAST_ADVERSE_R==-.25 and m.FAILFAST_WINDOW_H==4
    assert {x["id"] for x in m.PATH_HYPOTHESES}=={"DELAY_ENTRY_1H_CONFIRM","EARLY_MOMENTUM_FAILFAST_EXIT"}


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
