#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt
import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
PORTFOLIO = ROOT / 'status/paper-portfolio-10k-analyst-latest.json'
INTEGRITY = ROOT / 'status/paper-portfolio-10k-analyst-integrity.json'
ATTRIBUTION = ROOT / 'status/analyst-forward-attribution-latest.json'
OUT = ROOT / 'status/product-readiness-latest.json'
SCHEMA = 'ATLAS_PRODUCT_READINESS_GATE_V1'
CONTRACT = 'analyst_output'
HORIZON = '4-12H'
MIN_MATURED_12H = 30
MIN_DIRECTIONAL_MATURED = 5


def load(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _bool_check(name, passed, observed=None, required=None, severity='BLOCKER'):
    return {
        'name': name,
        'passed': bool(passed),
        'observed': observed,
        'required': required,
        'severity': severity,
    }


def build(portfolio=None, integrity=None, attribution=None):
    portfolio = portfolio if portfolio is not None else load(PORTFOLIO)
    integrity = integrity if integrity is not None else load(INTEGRITY)
    attribution = attribution if attribution is not None else load(ATTRIBUTION)

    checks = []
    checks.append(_bool_check('CANONICAL_ANALYST_CONTRACT', bool(portfolio) and portfolio.get('canonical_contract') == CONTRACT, None if not portfolio else portfolio.get('canonical_contract'), CONTRACT))
    checks.append(_bool_check('CANONICAL_4_12H_HORIZON', bool(portfolio) and portfolio.get('product_horizon') == HORIZON, None if not portfolio else portfolio.get('product_horizon'), HORIZON))
    checks.append(_bool_check('ANALYSIS_ONLY_NO_LIVE_EXECUTION', bool(portfolio) and portfolio.get('live_execution') is False and portfolio.get('can_override_production') is False, None if not portfolio else {'live_execution': portfolio.get('live_execution'), 'can_override_production': portfolio.get('can_override_production')}, {'live_execution': False, 'can_override_production': False}))
    checks.append(_bool_check('APPEND_ONLY_FORWARD_LEDGER', bool(integrity) and integrity.get('append_only_verified') is True, None if not integrity else integrity.get('append_only_verified'), True))
    checks.append(_bool_check('ATTRIBUTION_IS_EVIDENCE_ONLY', bool(attribution) and attribution.get('analysis_only') is True and attribution.get('live_execution') is False and attribution.get('can_override_production') is False and attribution.get('can_change_score') is False and attribution.get('can_change_threshold') is False, None if not attribution else {'analysis_only': attribution.get('analysis_only'), 'live_execution': attribution.get('live_execution'), 'can_override_production': attribution.get('can_override_production'), 'can_change_score': attribution.get('can_change_score'), 'can_change_threshold': attribution.get('can_change_threshold')}, {'analysis_only': True, 'live_execution': False, 'can_override_production': False, 'can_change_score': False, 'can_change_threshold': False}))

    trades = list((portfolio or {}).get('trades') or [])
    matured = [t for t in trades if ((t.get('settlement') or {}).get('terminal') is True)]
    direction_counts = Counter(str(t.get('direction') or 'UNKNOWN').upper() for t in matured)
    portfolio_stats = (portfolio or {}).get('portfolio') or {}
    matured_n = len(matured)
    checks.append(_bool_check('MINIMUM_MATURED_12H_SAMPLE', matured_n >= MIN_MATURED_12H, matured_n, MIN_MATURED_12H, 'EVIDENCE_BLOCKER'))
    for direction in ('LONG', 'SHORT'):
        checks.append(_bool_check(f'MINIMUM_{direction}_MATURED_SAMPLE', direction_counts.get(direction, 0) >= MIN_DIRECTIONAL_MATURED, direction_counts.get(direction, 0), MIN_DIRECTIONAL_MATURED, 'EVIDENCE_BLOCKER'))

    avg_r = portfolio_stats.get('avg_r')
    net_r = portfolio_stats.get('net_r')
    checks.append(_bool_check('POSITIVE_FORWARD_AVERAGE_R', matured_n >= MIN_MATURED_12H and isinstance(avg_r, (int, float)) and avg_r > 0, avg_r, '> 0 after minimum sample', 'EVIDENCE_BLOCKER'))
    checks.append(_bool_check('POSITIVE_FORWARD_NET_R', matured_n >= MIN_MATURED_12H and isinstance(net_r, (int, float)) and net_r > 0, net_r, '> 0 after minimum sample', 'EVIDENCE_BLOCKER'))

    technical_names = {'CANONICAL_ANALYST_CONTRACT','CANONICAL_4_12H_HORIZON','ANALYSIS_ONLY_NO_LIVE_EXECUTION','APPEND_ONLY_FORWARD_LEDGER','ATTRIBUTION_IS_EVIDENCE_ONLY'}
    technical_ready = all(c['passed'] for c in checks if c['name'] in technical_names)
    evidence_ready = all(c['passed'] for c in checks if c['severity'] == 'EVIDENCE_BLOCKER')

    if not technical_ready:
        state = 'BLOCKED_TECHNICAL'
    elif not evidence_ready:
        state = 'TECHNICALLY_READY_EVIDENCE_PENDING'
    else:
        state = 'FORWARD_EVIDENCE_GATE_PASSED'

    blockers = [c for c in checks if not c['passed']]
    return {
        'schema': SCHEMA,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'product_identity': 'CRYPTO_TRADE_INTELLIGENCE_AND_ANALYSIS_SYSTEM',
        'canonical_contract': CONTRACT,
        'product_horizon': HORIZON,
        'analysis_only': True,
        'live_execution': False,
        'can_override_production': False,
        'production_score_threshold_changed': False,
        'state': state,
        'technical_ready': technical_ready,
        'forward_evidence_ready': evidence_ready,
        'claim_policy': {
            'may_claim_technically_operational': technical_ready,
            'may_claim_forward_edge_validated': evidence_ready,
            'may_claim_profitable': False,
            'note': 'Profitability remains a stronger claim than this gate; fees/slippage/funding and larger independent forward evidence remain required.',
        },
        'preregistered_evidence_requirements': {
            'minimum_matured_12h_entries': MIN_MATURED_12H,
            'minimum_matured_per_direction': MIN_DIRECTIONAL_MATURED,
            'average_r': '> 0',
            'net_r': '> 0',
        },
        'observed': {
            'entries': len(trades),
            'matured_12h_terminal': matured_n,
            'matured_by_direction': dict(sorted(direction_counts.items())),
            'avg_r': avg_r,
            'net_r': net_r,
            'append_only_verified': None if not integrity else integrity.get('append_only_verified'),
            'attribution_context_complete': None if not attribution else ((attribution.get('counts') or {}).get('context_complete')),
        },
        'checks': checks,
        'blockers': blockers,
    }


def main():
    out = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'state': out['state'], 'technical_ready': out['technical_ready'], 'forward_evidence_ready': out['forward_evidence_ready'], 'blockers': [b['name'] for b in out['blockers']]}, sort_keys=True))


if __name__ == '__main__':
    main()
