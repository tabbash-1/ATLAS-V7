from pathlib import Path

WORKFLOW = Path(".github/workflows/atlas-production-snapshot.yml")


def test_production_snapshot_scopes_v4_before_asserting_v5():
    text = WORKFLOW.read_text(encoding="utf-8")
    generator = text.index("python3 offline_production_path_settlement.py")
    v4 = text.index('ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V4_EXECUTION_ELIGIBLE', generator)
    scope = text.index("python3 scope_production_path_settlement.py", v4)
    v5 = text.index('ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V5_SCOPED_NO_FAKE_REALIZED_R', scope)
    assert generator < v4 < scope < v5


def test_scoped_v5_forbids_fake_realized_r():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '.upstream_schema == "ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V4_EXECUTION_ELIGIBLE"' in text
    assert '.realized_r_scope == "ACTUAL_LIVE_FILL_LEDGER_ONLY"' in text
    assert '.realized_r_available == false' in text
    assert '.execution_ready_shadow_is_realized_r == false' in text
    assert '.plan_shadow_is_realized_r == false' in text
    assert '.summary.reason == "LIVE_EXECUTION_DISABLED_NO_ACTUAL_FILL_LEDGER"' in text
