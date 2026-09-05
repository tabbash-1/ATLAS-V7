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
    assert 'TRADE READY' not in js
    assert '$10K Canonical Forward Evaluation' in js
    assert 'analyst_output LONG/SHORT evaluations only' in js
    assert 'STALE_HOURS=2' in js
    assert 'history only, not current market data' in js


def test_research_ui_is_explicit_shadow_cohort():
    js = Path('atlas-research-validation-ui.js').read_text()
    assert 'Research Shadow Cohorts' in js
    assert 'Separate dataset from the $10K Canonical Forward Evaluation' in js
    assert 'shadow observations' in js
    assert 'RESEARCH ONLY' in js
    assert 'can_override_production:false' in js
    assert 'can_change_threshold:false' in js
