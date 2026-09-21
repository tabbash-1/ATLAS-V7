from pathlib import Path


WORKFLOW = Path('.github/workflows/atlas-reasoning-prospective-evidence.yml')


def test_reasoning_workflow_has_real_path_entries_not_literal_newlines():
    text = WORKFLOW.read_text()
    assert "'tests/test_market_context_hourly_runner.py'\\n" not in text
    expected = [
        'tests/test_market_context_hourly_runner.py',
        'tests/test_reasoning_immutable_ledger.py',
        'tests/test_market_context_forward_evidence.py',
        'tests/test_market_context_settlement_cost.py',
    ]
    for path in expected:
        assert f"      - '{path}'" in text


def test_reasoning_workflow_runs_contract_test():
    text = WORKFLOW.read_text()
    assert 'tests/test_reasoning_workflow_contract.py' in text
