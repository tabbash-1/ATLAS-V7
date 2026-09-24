from production_trade_plan import build

def row(votes=4, rv=.9, continuation=True, breakout=False):
    return {"ok":True,"candidate_direction":"SHORT","entry":100.0,
      "indicators":{"atr14":2.0},"direction_votes":votes,"relative_volume":rv,
      "structural_geometry":{"continuation_strong":continuation,"obstacle_price":94.0,
        "breakout":{"confirmed":breakout,"prior_24h_low":94.0,"prior_24h_high":106.0}}}

def test_strong_continuation_can_be_current_entry_trigger():
    out=build(row())
    assert out["analysis_ready"] is True
    assert out["entry_mode"]=="NOW"
    assert out["geometry_provenance"]["continuation_entry_trigger"] is True

def test_weak_participation_does_not_promote():
    out=build(row(rv=.5))
    assert out["analysis_ready"] is False

def test_three_votes_does_not_promote_continuation():
    out=build(row(votes=3))
    assert out["analysis_ready"] is False
