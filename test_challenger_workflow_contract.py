from pathlib import Path


def test_challenger_workflow_runs_forward_measurement_without_write_access():
    text=Path('.github/workflows/atlas-challenger-shadow.yml').read_text()
    assert "cron: '17 */4 * * *'" in text
    assert 'status/wait-missed-opportunity-latest.json' in text
    assert 'python atlas_challenger_shadow.py' in text
    assert 'actions/upload-artifact@v4' in text
    assert 'contents: read' in text
    assert 'contents: write' not in text
