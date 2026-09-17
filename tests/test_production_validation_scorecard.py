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
