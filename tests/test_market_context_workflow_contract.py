from pathlib import Path


def test_market_context_workflow_paths_are_individual_entries():
    workflow = Path('.github/workflows/atlas-market-context-reasoning.yml').read_text()
    in_paths = False
    for raw in workflow.splitlines():
        stripped = raw.strip()
        if stripped == 'paths:':
            in_paths = True
            continue
        if in_paths and stripped == 'permissions:':
            break
        if in_paths and stripped.startswith('- '):
            value = stripped[2:].strip().strip("'\"")
            assert ' ' not in value, f'workflow path filter must be one path per entry: {value!r}'
