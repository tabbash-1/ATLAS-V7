from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'atlas-production-snapshot.yml'


def workflow_text():
    return WORKFLOW.read_text(encoding='utf-8')


def test_snapshot_checkout_tracks_current_main():
    src = workflow_text()
    assert 'ref: main' in src
    assert 'fetch-depth: 0' in src


def test_snapshot_publish_does_not_rebase_generated_commit():
    src = workflow_text()
    assert 'git pull --rebase origin main' not in src
    assert 'SNAPSHOT_PAYLOAD_DIR' in src
    assert 'git reset --hard origin/main' in src
    assert 'for publish_attempt in 1 2 3' in src
    assert 'git push origin HEAD:main' in src


def test_snapshot_publish_preserves_remote_history_then_appends_new_capture():
    src = workflow_text()
    assert 'snapshot-history-line.jsonl' in src
    assert "new_key=obj.get('captured_at')" in src
    assert "row.get('captured_at') == new_key" in src
    assert "history.open('a'" in src


if __name__ == '__main__':
    tests = [
        test_snapshot_checkout_tracks_current_main,
        test_snapshot_publish_does_not_rebase_generated_commit,
        test_snapshot_publish_preserves_remote_history_then_appends_new_capture,
    ]
    for test in tests:
        test()
    print(f'production snapshot publish race tests: {len(tests)} ok')
