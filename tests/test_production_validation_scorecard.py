import datetime as dt
import production_validation_scorecard as m


def row(when, r, direction="LONG", equity=10000, pnl=0, status=None, tp1=False):
    return {"captured_at": when, "captured_at_ms": int(dt.datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp()*1000), "decision_source_of_truth":"FINAL_TRADE_GATE", "direction":direction, "equity_after_usd":equity, "pnl_usd":pnl, "settlement":{"terminal":True,"r_multiple":r,"status":status or ("LOSS" if r < 0 else "EXPIRED"),"tp1_reached":tp1}}


def test_epoch_boundary_excludes_legacy():
    rows=[row("2026-09-11T00:00:00Z",2), row("2026-09-14T12:31:29Z",-1)]
    post=[x for x in rows if m._ts(x["captured_at"]) >= m.EPOCH_START]
    assert len(post)==1 and post[0]["settlement"]["r_multiple"]==-1


def test_summary_true_path_metrics():
    rows=[row("2026-09-15T00:00:00Z",2,"LONG",10200,200,"WIN_TP2",True), row("2026-09-16T00:00:00Z",-1,"SHORT",10100,-100,"LOSS",False), row("2026-09-17T00:00:00Z",.4,"SHORT",10140,40,"EXPIRED_TP1",True)]
    s=m._summarize(rows)
    assert s["terminal"]==3 and s["positive"]==2 and s["negative"]==1
    assert s["tp2_wins"]==1 and s["tp1_reached"]==2
    assert s["net_r"]==1.4 and s["profit_factor_r"]==2.4


def test_formal_sample_constant_is_locked():
    assert m.MIN_FORMAL_SAMPLE==30
    assert m.EPOCH_ID=="HTF_SR_V2_2026-09-14"


def test_no_profitability_claim_contract():
    assert m.SOURCE=="FINAL_TRADE_GATE"


def test_cost_model_matches_phase4_assumptions():
    x=row("2026-09-16T00:00:00Z",-1,"SHORT",9900,-100,"LOSS",False)
    x["captured_at_ms"]=1000000
    x["settlement"]["exit_at_ms"]=1000000+12*3600000
    x["paper_notional_usd"]=10000
    x["risk_usd"]=100
    z=m._cost_adjusted_row(x)
    assert z["estimated_cost_bps"]==17.0
    assert z["estimated_cost_usd"]==17.0
    assert z["estimated_cost_r"]==0.17
    assert z["net_r"]==-1.17


def test_early_exit_reduces_funding_component_not_roundtrip_cost():
    x=row("2026-09-16T00:00:00Z",-1,"LONG",9900,-100,"LOSS",False)
    x["captured_at_ms"]=1000000
    x["settlement"]["exit_at_ms"]=1000000+4*3600000
    x["paper_notional_usd"]=10000
    x["risk_usd"]=100
    z=m._cost_adjusted_row(x)
    assert z["estimated_cost_bps"]==16.3333
    assert z["net_r"]==-1.1633


def test_cost_summary_never_improves_gross_r_under_cost_assumption():
    a=row("2026-09-16T00:00:00Z",.5,"SHORT",10050,50,"EXPIRED_TP1",True)
    b=row("2026-09-17T00:00:00Z",-1,"LONG",9950,-100,"LOSS",False)
    for i,x in enumerate((a,b)):
        x["captured_at_ms"]=1000000+i*100000000
        x["settlement"]["exit_at_ms"]=x["captured_at_ms"]+12*3600000
        x["paper_notional_usd"]=5000
        x["risk_usd"]=100
    s=m._cost_summary([a,b])
    assert s["net_r"] < -.5
    assert s["estimated_total_cost_usd"] > 0
