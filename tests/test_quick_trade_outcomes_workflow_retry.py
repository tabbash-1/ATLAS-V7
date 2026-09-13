from pathlib import Path


def test_quick_trade_outcomes_retries_concurrent_main_pushes():
    workflow = Path('.github/workflows/atlas-quick-trade-outcomes.yml').read_text()

    assert 'for attempt in 1 2 3 4 5; do' in workflow
    assert 'git pull --rebase origin main' in workflow
    assert 'git push origin HEAD:main' in workflow
    assert 'Quick Trade outcomes push failed after 5 attempts' in workflow
    assert 'exit 1' in workflow
