from pathlib import Path
def test_snapshot_refreshes_canonical_settlement_before_edge_report():
    text=Path(".github/workflows/atlas-production-snapshot.yml").read_text()
    settle=text.index("name: Refresh canonical Production path settlement")
    edge=text.index("name: Build prospective edge report")
    assert settle < edge
    assert "python3 offline_production_path_settlement.py" in text
    assert 'ATLAS_OFFLINE_PRODUCTION_PATH_SETTLEMENT_V3_CANONICAL_FINAL_GATE' in text
    assert "status/production-path-settlement-latest.json" in text
