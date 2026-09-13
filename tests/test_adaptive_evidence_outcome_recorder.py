import pathlib
import tempfile

import adaptive_evidence_outcome_recorder as m


def _obs(side="LONG"):
    entry=100.0
    stop=98.5 if side=="LONG" else 101.5
    target=103.0 if side=="LONG" else 97.0
    return {
        "observation_id":"abc",
        "symbol":"XRPUSDT",
        "decision_bar_close_ms":1_000_000,
        "shadow_verdict":{"decision":"SHADOW_CANDIDATE","direction":side,"grade":"A"},
        "prospective_geometry":{"entry_reference":entry,"stop":stop,"target_2r":target,"horizon_h":12,"modeled_round_trip_cost_bps":10},
    }


def _bars(prices, start=1_000_000):
    out=[]
    for i,(lo,hi,close) in enumerate(prices):
        out.append({'t':start+i*3600_000,'o':close,'h':hi,'l':lo,'c':close,'v':1})
    return out


def test_long_target_settles_2r_less_cost():
    rows=_bars([(99.5,101,100.5),(100,103.2,103)])
    r=m.settle_geometry(_obs("LONG"),rows,now_ms=20*3600_000)
    assert r["outcome"]=="WIN_TP2"
    assert r["gross_r"]==2.0
    assert r["net_r"]<2.0
    assert r["positive_after_cost"] is True


def test_both_hit_is_stop_first():
    rows=_bars([(98,104,101)])
    r=m.settle_geometry(_obs("LONG"),rows,now_ms=20*3600_000)
    assert r["outcome"]=="LOSS_BOTH_STOP_FIRST"
    assert r["gross_r"]==-1.0


def test_unmatured_unhit_candidate_stays_open():
    rows=_bars([(99,101,100.2)]*3)
    r=m.settle_geometry(_obs("LONG"),rows,now_ms=1_000_000+3*3600_000)
    assert r is None


def test_mature_expiry_marks_to_market():
    rows=_bars([(99,101,100.3)]*12)
    r=m.settle_geometry(_obs("LONG"),rows,now_ms=1_000_000+13*3600_000)
    assert r["outcome"]=="EXPIRED"
    assert -1 <= r["gross_r"] <= 2


def test_wait_is_never_settled_as_trade():
    o=_obs("LONG")
    o["shadow_verdict"]["decision"]="WAIT"
    assert m.settle_geometry(o,_bars([(98,104,101)]),now_ms=20*3600_000) is None


def test_summary_uses_after_cost_r():
    s=m.summarize([{"net_r":1.8},{"net_r":-1.1}])
    assert s["n"]==2
    assert s["positive_after_cost"]==1
    assert s["net_r"]==0.7


def test_contract_flags_are_fail_closed():
    with tempfile.TemporaryDirectory() as d:
        status=pathlib.Path(d)/"status"
        (status/"history").mkdir(parents=True)
        (status/"history"/"adaptive-evidence-shadow-observations.jsonl").write_text("")
        r=m.record(str(status),now_ms=1,fetcher=lambda *a:[])
    assert r["research_only"] is True
    assert r["paper_only"] is True
    assert r["live_execution"] is False
    assert r["can_override_production"] is False
    assert r["production_threshold_unchanged"]==68
