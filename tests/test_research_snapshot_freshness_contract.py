from pathlib import Path


def test_web_only_exposes_research_snapshot_age_and_staleness():
    src = Path('cloud_web_only.py').read_text(encoding='utf-8')
    assert 'RESEARCH_SNAPSHOT_STALE_HOURS = 6.0' in src
    assert "'snapshot_age_hours'" in src
    assert "'snapshot_stale'" in src
    assert "'current_for_research'" in src
    assert "'can_override_production'" in src


def test_research_monitors_never_restamp_or_commit_cached_results():
    for name in (
        '.github/workflows/atlas-historical-evaluation-snapshot.yml',
        '.github/workflows/atlas-prospective-microstructure-snapshot.yml',
    ):
        text = Path(name).read_text(encoding='utf-8')
        assert 'contents: read' in text
        assert '_snapshot_captured_at' not in text
        assert 'git commit' not in text
        assert 'git push' not in text
        assert 'MONITOR_ONLY' in text
        assert 'COMMITTED_GITHUB_ACTIONS_SNAPSHOT' in text
