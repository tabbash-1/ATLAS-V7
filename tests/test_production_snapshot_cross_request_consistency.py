from pathlib import Path


WORKFLOW = Path('.github/workflows/atlas-production-snapshot.yml')


def test_cross_request_ai_reference_drift_is_not_a_hard_canonical_mismatch():
    text = WORKFLOW.read_text()
    assert "reference_drift=[]" in text
    assert "temporal_drift=(" in text
    assert "mismatch=ref.get('canonical_source_present') is not True" in text
    assert "if temporal_drift and s in core_symbols: reference_drift.append" in text


def test_snapshot_exposes_reference_drift_separately_from_canonical_consistency():
    text = WORKFLOW.read_text()
    assert "'reference_drift_count':len(reference_drift)" in text
    assert "'reference_drift':reference_drift" in text
    assert "'mismatch_count':len(consistency)" in text
