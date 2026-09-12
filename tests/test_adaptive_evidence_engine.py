from adaptive_evidence_engine import evaluate, VERSION


def test_xrp_long_requires_htf_1h_rsi():
    r = evaluate("XRPUSDT", "LONG", htf_4h="LONG", htf_12h="LONG", confirm_1h=True, rsi_aligned=True)
    assert r["decision"] == "SHADOW_CANDIDATE"
    assert r["grade"] == "A"
    assert r["can_override_production"] is False


def test_xrp_structure_upgrades_grade_only():
    r = evaluate("XRPUSDT", "LONG", htf_4h="LONG", htf_12h="LONG", confirm_1h=True, rsi_aligned=True, structure_break=True)
    assert r["grade"] == "A+"


def test_xrp_missing_1h_waits():
    r = evaluate("XRPUSDT", "LONG", htf_4h="LONG", htf_12h="LONG", rsi_aligned=True)
    assert r["decision"] == "WAIT"


def test_zec_requires_structure_and_volume():
    r = evaluate("ZECUSDT", "LONG", htf_4h="LONG", htf_12h="LONG", structure_break=True, volume_confirmed=True)
    assert r["decision"] == "SHADOW_CANDIDATE"
    assert r["grade"] == "A"


def test_zec_1h_upgrades_but_rsi_not_required():
    r = evaluate("ZECUSDT", "SHORT", htf_4h="SHORT", htf_12h="SHORT", confirm_1h=True, structure_break=True, volume_confirmed=True, rsi_aligned=False)
    assert r["decision"] == "SHADOW_CANDIDATE"
    assert r["grade"] == "A+"


def test_htf_conflict_fails_closed():
    r = evaluate("XRPUSDT", "LONG", htf_4h="LONG", htf_12h="SHORT", confirm_1h=True, rsi_aligned=True, structure_break=True)
    assert r["decision"] == "WAIT"


def test_unvalidated_asset_stays_wait():
    r = evaluate("BTCUSDT", "LONG", htf_4h="LONG", htf_12h="LONG", confirm_1h=True, rsi_aligned=True, structure_break=True, volume_confirmed=True)
    assert r["decision"] == "WAIT"
    assert "ASSET_DIRECTION_MODEL_NOT_VALIDATED" in r["reasons"]


def test_contract():
    r = evaluate("XRPUSDT", "LONG", htf_4h="LONG", htf_12h="LONG", confirm_1h=True, rsi_aligned=True)
    assert r["version"] == VERSION
    assert r["research_only"] is True
    assert r["can_execute"] is False
    assert r["production_threshold_unchanged"] == 68
