from pathlib import Path

import committed_research_api as api


def test_report_registry_tracks_current_committed_schemas():
    expected = {
        '/api/research/offline-forward-evaluation': 'ATLAS_OFFLINE_FORWARD_EVALUATION_V4_CANONICAL_TRUTH',
        '/api/research/forward-robustness-guardrails': 'ATLAS_FORWARD_ROBUSTNESS_GUARDRAILS_V2_CANONICAL_TRUTH',
        '/api/research/prospective-direction-guardrail': 'ATLAS_PROSPECTIVE_DIRECTION_GUARDRAIL_V1_4H',
        '/api/research/paper-portfolio-10k': 'ATLAS_PAPER_10K_ANALYST_OUTPUT_V1',
        '/api/research/learning-engine': 'ATLAS_LEARNING_ENGINE_V1',
    }
    assert {route: spec[1] for route, spec in api.REPORTS.items()} == expected


def test_all_committed_reports_load_without_schema_mismatch():
    base = Path('.')
    for route, spec in api.REPORTS.items():
        payload = api._load(base, *spec)
        assert payload['ok'] is True, (route, payload.get('error'))
        assert payload['schema'] == spec[1]
        assert payload.get('live_execution') is False or (payload.get('safety') or {}).get('live_execution') is False
        assert payload.get('can_override_production') is False or (payload.get('safety') or {}).get('can_override_production') is False


if __name__ == '__main__':
    test_report_registry_tracks_current_committed_schemas()
    test_all_committed_reports_load_without_schema_mismatch()
    print('committed research API schema sync: ok')
