from pathlib import Path

workflow = Path('.github/workflows/atlas-profitability-feature-attribution.yml').read_text()

assert 'for attempt in 1 2 3 4 5; do' in workflow
assert 'git pull --rebase origin main' in workflow
assert 'git push origin HEAD:main' in workflow
assert 'Concurrent main update detected; retrying push' in workflow
assert 'Failed to publish attribution artifact after 5 concurrent-update retries' in workflow

print('profitability feature attribution workflow push-race regression: PASS')
