from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / ".github/workflows/atlas-paper-portfolio-10k.yml"
FORWARD = ROOT / ".github/workflows/atlas-offline-forward-evaluation.yml"
SNAPSHOT = ROOT / ".github/workflows/atlas-canonical-outcome-snapshot.yml"
CANONICAL = "status/canonical-outcomes-latest.json"
BUILDER = "python canonical_outcome_snapshot.py"


def test_canonical_snapshot_has_single_publication_owner():
    paper = PAPER.read_text(encoding="utf-8")
    forward = FORWARD.read_text(encoding="utf-8")
    snapshot = SNAPSHOT.read_text(encoding="utf-8")
    assert BUILDER not in paper
    assert BUILDER not in forward
    assert CANONICAL not in paper
    assert CANONICAL not in forward
    assert BUILDER in snapshot
    assert CANONICAL in snapshot
    assert "scripts/commit_status_with_retry.sh" in snapshot
    assert "group: atlas-canonical-outcome-snapshot" in snapshot
    assert "cancel-in-progress: false" in snapshot


def test_source_publishers_trigger_canonical_owner():
    snapshot = SNAPSHOT.read_text(encoding="utf-8")
    assert "status/paper-portfolio-10k-latest.json" in snapshot
    assert "status/offline-forward-evaluation-latest.json" in snapshot


def test_canonical_outcome_migration_preserves_only_proven_prospective_entries():
    text = (ROOT / "canonical_outcome_snapshot.py").read_text(encoding="utf-8")
    assert 'legacy_prospective_eligible = (' in text
    assert 'row.get("decision_action") == "TRADE_READY"' in text
    assert 'row.get("canonical_truth_schema") == "ATLAS_CANONICAL_DECISION_TRUTH_V1"' in text
    assert 'row.get("paper_only") is True' in text
    assert 'row.get("live_execution") is False' in text
    assert 'execution_eligibility_provenance' in text
    assert 'row["execution_ready_at_capture"] = True' in text


def test_canonical_outcome_summary_uses_nested_settlement_truth():
    text = (ROOT / "canonical_outcome_snapshot.py").read_text(encoding="utf-8")
    assert '(r.get("settlement") or {}).get("r_multiple")' in text
    assert 'r.get("r_multiple")' not in text
    assert 'EXPLICIT_READY_OR_PROVEN_LEGACY_PROSPECTIVE_CANONICAL_ENROLLMENT' in text


def test_canonical_outcome_summary_reports_drawdown_from_strict_settled_rows():
    text = (ROOT / "canonical_outcome_snapshot.py").read_text(encoding="utf-8")
    assert 'drawdowns = [float(r["drawdown_after_pct"]) for r in settled' in text
    assert '"max_drawdown_pct": round(max(drawdowns), 4) if drawdowns else None' in text


def test_evidence_publishers_checkout_correct_revision_before_generation():
    paper = PAPER.read_text(encoding="utf-8")
    assert "ref: ${{ github.event_name == 'pull_request' && github.sha || 'main' }}" in paper
    assert "fetch-depth: 0" in paper

    # Scheduled/push evidence owners still generate from latest main.
    for path in (FORWARD, SNAPSHOT):
        text = path.read_text(encoding="utf-8")
        assert "ref: main" in text
        assert "fetch-depth: 0" in text


def test_source_publishers_use_safe_status_writer():
    paper = PAPER.read_text(encoding="utf-8")
    forward = FORWARD.read_text(encoding="utf-8")
    assert "scripts/commit_status_with_retry.sh" in paper
    assert "scripts/commit_status_with_retry.sh" in forward
    assert "git pull --rebase origin main" not in forward
