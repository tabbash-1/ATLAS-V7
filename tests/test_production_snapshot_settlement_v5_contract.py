from pathlib import Path


def test_production_snapshot_requires_scoped_settlement_v5_contract():
    workflow = Path('.github/workflows/atlas-production-snapshot.yml').read_text(encoding='utf-8')

    assert 'ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V5_SCOPED_NO_FAKE_REALIZED_R' in workflow
    assert '.upstream_schema == "ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V4_EXECUTION_ELIGIBLE"' in workflow
    assert '.realized_r_available == false' in workflow
    assert '.realized_r_scope == "ACTUAL_LIVE_FILL_LEDGER_ONLY"' in workflow
    assert '.summary.available == false' in workflow
    assert '.summary.reason == "LIVE_EXECUTION_DISABLED_NO_ACTUAL_FILL_LEDGER"' in workflow
