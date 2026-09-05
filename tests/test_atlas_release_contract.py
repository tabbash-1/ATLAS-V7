from pathlib import Path
import json

from atlas_release_contract import build_product_status, RELEASE_VERSION


def _write(tmp_path, payload):
    status = tmp_path / 'status'
    status.mkdir(parents=True, exist_ok=True)
    (status / 'product-readiness-latest.json').write_text(json.dumps(payload), encoding='utf-8')


def test_technically_ready_can_ship_with_evidence_pending(tmp_path):
    _write(tmp_path, {
        'technical_ready': True,
        'canonical_contract': 'analyst_output',
        'product_horizon': '4-12H',
        'analysis_only': True,
        'live_execution': False,
        'production_score_threshold_changed': False,
        'forward_evidence_ready': False,
        'state': 'TECHNICALLY_READY_EVIDENCE_PENDING',
        'claim_policy': {'may_claim_technically_operational': True, 'may_claim_profitable': False},
        'observed': {'entries': 3, 'matured_12h_terminal': 0},
    })
    out = build_product_status(tmp_path)
    assert out['ok'] is True
    assert out['product_status'] == 'READY_FOR_ANALYSIS'
    assert out['release_version'] == RELEASE_VERSION
    assert out['forward_validation'] == 'EVIDENCE_PENDING'
    assert out['profitability_validated'] is False
    assert out['analysis_only'] is True
    assert out['live_execution'] is False
    assert out['order_routing'] is False
    assert out['score_or_threshold_changed_by_release'] is False


def test_release_fails_closed_if_technical_contract_breaks(tmp_path):
    _write(tmp_path, {
        'technical_ready': True,
        'canonical_contract': 'trade_plan',
        'product_horizon': '4-12H',
        'analysis_only': True,
        'live_execution': False,
        'production_score_threshold_changed': False,
        'forward_evidence_ready': False,
    })
    out = build_product_status(tmp_path)
    assert out['ok'] is False
    assert out['product_status'] == 'NOT_READY'
    assert out['can_override_production'] is False


def test_missing_readiness_snapshot_fails_closed(tmp_path):
    out = build_product_status(tmp_path)
    assert out['ok'] is False
    assert out['product_status'] == 'NOT_READY'
    assert out['readiness_snapshot_error']
