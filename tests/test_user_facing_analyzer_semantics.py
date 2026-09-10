from pathlib import Path


def test_unified_polish_has_no_execution_language():
    js = Path('atlas-unified-terminal-polish.js').read_text()
    assert 'execution stays WAIT' not in js
    assert '<strong>Execution:</strong>' not in js
    assert 'no order routing' in js
    assert 'RAW QUALIFICATION' in js
    assert 'RAW GEOMETRY' in js
    assert 'QUALITY GATE' in js


def test_canonical_forward_ui_is_distinct_and_stale_aware():
    js = Path('atlas-paper-portfolio-ui.js').read_text()
    # This is now the canonical Final Trade Gate paper ledger. It may describe
    # canonical TRADE READY entries, but it must never substitute research/shadow
    # observations or historical backfill into the portfolio P&L.
    assert '$10K Canonical Paper Portfolio' in js
    assert 'FINAL_TRADE_GATE' in js
    assert 'Research/shadow analyst_output never counts as portfolio P&amp;L.' in js
    assert 'no research substitution' in js
    assert "source_of_truth:'FINAL_TRADE_GATE'" in js
    assert 'legacy_backfill_allowed!==false' in js
    assert 'STALE_HOURS=2' in js
    assert 'paper_only:true' in js
    assert 'live_execution:false' in js
    assert 'can_override_production:false' in js


def test_research_ui_is_explicit_shadow_cohort():
    js = Path('atlas-research-validation-ui.js').read_text()
    assert 'Research Shadow Cohorts' in js
    assert 'Separate dataset from the $10K Canonical Forward Evaluation' in js
    assert 'shadow observations' in js
    assert 'RESEARCH ONLY' in js
    assert 'can_override_production:false' in js
    assert 'can_change_threshold:false' in js
