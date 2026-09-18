from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def text(name):
    return (ROOT/".github/workflows"/name).read_text(encoding="utf-8")


def test_paper_commit_does_not_suppress_scorecard_trigger():
    y=text("atlas-paper-portfolio-10k.yml")
    assert "paper: update prospective 10k portfolio [skip render]" in y
    assert "paper: update prospective 10k portfolio [skip ci]" not in y


def test_scorecard_commit_does_not_suppress_downstream_diagnostics():
    y=text("atlas-production-validation-scorecard.yml")
    assert "validation: update post-V2 production scorecard [skip render]" in y
    assert "validation: update post-V2 production scorecard [skip ci]" not in y


def test_scorecard_listens_to_canonical_outcome_status():
    y=text("atlas-production-validation-scorecard.yml")
    assert "status/canonical-outcomes-latest.json" in y


def test_attribution_and_provenance_listen_to_scorecard_status():
    a=text("atlas-production-failure-attribution.yml")
    c=text("atlas-entry-provenance-cohort.yml")
    assert "status/production-validation-latest.json" in a
    assert "status/production-validation-latest.json" in c


def test_scorecard_chains_from_paper_workflow_run_not_token_push_only():
    y=text("atlas-production-validation-scorecard.yml")
    assert "workflow_run:" in y
    assert "ATLAS $10K Paper Portfolio" in y
    assert "github.event.workflow_run.conclusion == 'success'" in y
    assert "github.event.workflow_run.head_branch == 'main'" in y


def test_diagnostics_chain_from_scorecard_workflow_run():
    for name in ("atlas-production-failure-attribution.yml","atlas-entry-provenance-cohort.yml"):
        y=text(name)
        assert "workflow_run:" in y
        assert "ATLAS Production Validation Scorecard" in y
        assert "github.event.workflow_run.conclusion == 'success'" in y
        assert "github.event.workflow_run.head_branch == 'main'" in y
