from pathlib import Path

def test_adp_v7_final_status_blocks_commercial_readiness():
    text=Path("research/adp/FINAL_EVIDENCE_V7.md").read_text()
    assert "NOT READY" in text
    assert "passed = false" in text
    assert "must not be merged into ATLAS Production" in text

def test_adp_v7_holdout_is_research_only():
    src=Path("research/adp/v7_frozen_holdout.py").read_text()
    assert '"research_only":True' in src
    assert '"production_effect":"NONE"' in src
    assert 'positive>=7' in src
