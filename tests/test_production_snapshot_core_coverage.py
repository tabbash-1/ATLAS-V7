from pathlib import Path


def test_production_snapshot_retries_and_requires_complete_core_coverage():
    workflow = Path('.github/workflows/atlas-production-snapshot.yml').read_text(encoding='utf-8')

    # The seven canonical product assets are strict. HYPE remains an extra monitored asset.
    assert "core_symbols=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT']" in workflow
    assert "canonical_snapshot_complete" in workflow
    assert "canonical_coverage_pct" in workflow
    assert "failed_core_symbols" in workflow

    # A transient endpoint failure must receive an explicit second pass before the
    # workflow decides whether the canonical cycle is complete.
    assert 'Second-pass recovery for failed canonical decisions' in workflow
    assert 'CANONICAL_CORE_SNAPSHOT_INCOMPLETE' in workflow

    # The contract step must reject an incomplete seven-asset cycle instead of
    # committing a successful-looking snapshot containing an HTTP/JSON failure.
    assert '.canonical_coverage.canonical_snapshot_complete == true' in workflow
