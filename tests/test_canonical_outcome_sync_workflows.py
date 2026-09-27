from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / ".github/workflows/atlas-paper-portfolio-10k.yml"
FORWARD = ROOT / ".github/workflows/atlas-offline-forward-evaluation.yml"
CANONICAL = "status/canonical-outcomes-latest.json"
BUILDER = "python canonical_outcome_snapshot.py"


def _assert_producer_sync(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert BUILDER in text, f"{path.name} must rebuild canonical outcomes in-process"
    assert CANONICAL in text, f"{path.name} must commit the rebuilt canonical outcome snapshot"
    build_pos = text.index(BUILDER)
    markers = [
        x for x in (
            text.find("git commit", build_pos),
            text.find("commit_status_with_retry.sh", build_pos),
        ) if x >= 0
    ]
    assert markers, f"{path.name} must publish the rebuilt canonical outcome snapshot"
    commit_pos = min(markers)
    assert build_pos < commit_pos, f"{path.name} must rebuild canonical outcomes before committing"


def test_paper_portfolio_refreshes_canonical_outcomes_atomically():
    _assert_producer_sync(PAPER)


def test_offline_forward_refreshes_canonical_outcomes_atomically():
    _assert_producer_sync(FORWARD)


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


def test_canonical_outcome_writers_share_one_serial_concurrency_group():
    paper = PAPER.read_text(encoding="utf-8")
    forward = FORWARD.read_text(encoding="utf-8")
    assert "group: atlas-canonical-outcome-writers" in paper
    assert "group: atlas-canonical-outcome-writers" in forward
    assert "cancel-in-progress: false" in paper
    assert "cancel-in-progress: false" in forward


def test_offline_forward_uses_shared_status_writer():
    text = FORWARD.read_text(encoding="utf-8")
    assert "scripts/commit_status_with_retry.sh" in text
    assert "git pull --rebase origin main" not in text
