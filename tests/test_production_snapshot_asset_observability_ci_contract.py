from pathlib import Path


WORKFLOW = Path('.github/workflows/production-snapshot-asset-observability-ci.yml')


def test_snapshot_observability_ci_installs_pytest_before_running_regression_contract():
    text = WORKFLOW.read_text(encoding='utf-8')

    install = 'python -m pip install pytest'
    regression = 'python -m pytest -q tests/test_production_snapshot_asset_observability.py tests/test_production_snapshot_asset_observability_ci_contract.py'

    assert install in text
    assert regression in text
    assert text.index(install) < text.index(regression)
