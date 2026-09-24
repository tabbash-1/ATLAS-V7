from production_trade_plan import build


def row(votes=4, rv=.9, continuation=True, breakout=False):
    return {"ok": True, "candidate_direction": "SHORT", "entry": 100.0,
      "indicators": {"atr14": 2.0}, "direction_votes": votes, "relative_volume": rv,
      "structural_geometry": {"continuation_strong": continuation, "obstacle_price": 94.0,
        "breakout": {"confirmed": breakout, "prior_24h_low": 94.0, "prior_24h_high": 106.0}}}


def test_continuation_alone_cannot_promote_without_forward_evidence():
    out = build(row(votes=4, rv=.9, continuation=True, breakout=False))
    assert out["analysis_ready"] is False
    assert out["analysis_action"] == "WAIT"
    assert out["execution_ready"] is False


def test_confirmed_breakout_remains_current_entry_trigger():
    out = build(row(breakout=True))
    assert out["analysis_ready"] is True
    assert out["entry_mode"] == "NOW"
    assert out["analysis_action"] == "SHORT"
