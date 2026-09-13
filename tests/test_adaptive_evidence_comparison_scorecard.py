import adaptive_evidence_comparison_scorecard as m


def _adaptive(n=0):
    return {"cost_basis_bps":10,"settled_candidates":n,"overall":{"n":n,"positive_pct":50.0 if n else 0.0,"avg_net_r":0.2 if n else 0.0,"net_r":2.0 if n else 0.0,"profit_factor":1.3 if n else 0.0}}


def _canonical(n=3):
    return {"path_summary":{"entries":n,"closed":n,"win_rate_pct":66.67,"avg_r":0.5,"net_r":1.5,"profit_factor":2.5,"max_drawdown_pct":1.0}}


def test_early_samples_block_comparison():
    r=m.build(_adaptive(0),_canonical(3))
    assert r["comparison"]["allowed"] is False
    assert r["comparison"]["verdict"]=="INSUFFICIENT_DATA"
    assert r["adaptive_shadow_forward"]["sample_status"]=="EARLY_INSUFFICIENT_SAMPLE"
    assert r["canonical_production_forward"]["sample_status"]=="EARLY_INSUFFICIENT_SAMPLE"


def test_predeclared_floor_allows_initial_comparison_only():
    r=m.build(_adaptive(10),_canonical(10))
    assert r["comparison"]["allowed"] is True
    assert r["comparison"]["verdict"]=="COMPARISON_ALLOWED_NOT_CAUSAL_PROOF"


def test_lanes_never_pool_or_override_production():
    r=m.build(_adaptive(20),_canonical(20))
    assert r["lanes_are_separate"] is True
    assert r["samples_are_not_pooled"] is True
    assert r["can_override_production"] is False
    assert r["live_execution"] is False
    assert r["production_threshold_unchanged"]==68


def test_cost_basis_is_explicitly_different():
    r=m.build(_adaptive(10),_canonical(10))
    assert r["adaptive_shadow_forward"]["cost_basis_bps"]==10
    assert r["canonical_production_forward"]["cost_basis"]=="GROSS_CANONICAL_COSTS_NOT_DEDUCTED"
    assert "must not be claimed" in r["comparison"]["important_note"]
