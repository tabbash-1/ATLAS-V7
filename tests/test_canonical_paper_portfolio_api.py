from pathlib import Path

import committed_research_api as api


def test_paper_portfolio_endpoint_uses_canonical_analyst_output_source():
    filename, schema, kind = api.REPORTS['/api/research/paper-portfolio-10k']
    assert filename == 'paper-portfolio-10k-analyst-latest.json'
    assert schema == 'ATLAS_PAPER_10K_ANALYST_OUTPUT_V1'
    assert kind == 'paper'


def test_canonical_analyst_paper_snapshot_loads_and_preserves_safety_contract():
    payload = api._load(
        Path(__file__).resolve().parents[1],
        'paper-portfolio-10k-analyst-latest.json',
        'ATLAS_PAPER_10K_ANALYST_OUTPUT_V1',
        'paper',
    )
    assert payload['ok'] is True
    assert payload['canonical_contract'] == 'analyst_output'
    assert payload['paper_only'] is True
    assert payload['live_execution'] is False
    assert payload['can_override_production'] is False
    assert payload['portfolio']['entries'] >= payload['portfolio']['closed']
    assert payload['portfolio']['starting_equity_usd'] == 10000.0
