from pathlib import Path


def test_web_only_serves_research_snapshots_without_background_refresh():
    src = Path('cloud_web_only.py').read_text(encoding='utf-8')

    assert "'/api/research/historical-evaluation'" in src
    assert "'/api/research/prospective-microstructure-validation'" in src
    assert "'COMMITTED_GITHUB_ACTIONS_SNAPSHOT'" in src
    assert "'background_workers': False" in src
    assert "'research_execution_location': 'GITHUB_ACTIONS'" in src
    assert "'research_snapshot_serving': 'COMMITTED_SNAPSHOT_ONLY'" in src
    assert "'web_process_refresh_triggered': False" in src
    assert "'web_process_background_worker': False" in src
    assert 'historical_evaluation_runtime' not in src
    assert 'prospective_microstructure_validation_runtime' not in src
