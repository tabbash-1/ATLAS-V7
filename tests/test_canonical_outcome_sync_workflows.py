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
