"""ATLAS 4-12H product quality gate.

This overlay does not change Production scores or the score threshold. It is a
fail-closed product decision guard derived from committed forward evidence. A
score-qualified setup can remain qualified for audit while the user-facing
4-12H analysis is demoted to WAIT when its setup family is under evidence
quarantine.
"""

VERSION = 'PRODUCT_QUALITY_GATE_V1_EVIDENCE_QUARANTINE'
PRODUCT_HORIZON = '4-12H'

# Only mature, clearly adverse clusters are quarantined. We intentionally do not
# blacklist symbols or all LONG decisions: that would overfit the observed month.
QUARANTINE = {
    ('LONG', 'TREND_UP', 'TREND_PULLBACK_LONG'): {
        'evidence_n12': 21,
        'mean12_pct': -2.58138,
        'positive12_pct': 14.29,
        'loss_ge_1_12_pct': 71.43,
        'source': 'status/monthly-product-audit-latest.json',
    },
    ('LONG', 'TREND_UP', 'MARKET_CONTINUATION_LONG'): {
        'evidence_n12': 10,
        'mean12_pct': -1.52820,
        'positive12_pct': 10.0,
        'loss_ge_1_12_pct': 80.0,
        'source': 'status/monthly-product-audit-latest.json',
    },
}


def _norm(value):
    return str(value or '').strip().upper()


def assess(row):
    direction = _norm(row.get('candidate_direction'))
    regime = _norm(row.get('regime'))
    playbook = _norm(row.get('playbook'))
    key = (direction, regime, playbook)
    evidence = QUARANTINE.get(key)
    if not evidence:
        return {
            'status': 'PASS',
            'reason': 'SETUP_NOT_IN_EVIDENCE_QUARANTINE',
            'product_horizon': PRODUCT_HORIZON,
            'can_change_score': False,
            'can_change_threshold': False,
            'live_execution': False,
        }
    return {
        'status': 'BLOCK',
        'reason': '4_12H_SETUP_FAMILY_FAILED_FORWARD_EVIDENCE_GATE',
        'product_horizon': PRODUCT_HORIZON,
        'quarantine_key': {'direction': direction, 'regime': regime, 'playbook': playbook},
        'evidence': dict(evidence),
        'status_change_conditions': [
            'SETUP_RECLASSIFIES_TO_NON_QUARANTINED_PLAYBOOK',
            'MARKET_REGIME_OR_STRUCTURE_RECLASSIFIES',
            'INDEPENDENT_FORWARD_EVIDENCE_REVALIDATES_THIS_SETUP_FAMILY',
        ],
        'can_change_score': False,
        'can_change_threshold': False,
        'live_execution': False,
    }


def install(atlas):
    original = atlas.production_decision

    def build(symbol):
        row = original(symbol)
        if not isinstance(row, dict) or not row.get('ok'):
            return row

        gate = assess(row)
        row['setup_quality_gate'] = gate
        row['quality_gate_version'] = VERSION
        row['production_score_preserved'] = True
        row['production_threshold_changed_by_quality_gate'] = False
        row['analysis_only'] = True
        row['live_execution'] = False

        if gate.get('status') != 'BLOCK':
            return row

        # Preserve raw qualification for audit; only the canonical user-facing
        # 4-12H analysis is demoted. This avoids rewriting history or tuning the
        # score threshold to make results look better.
        row['pre_quality_gate_actionable_decision'] = row.get('actionable_decision')
        row['pre_quality_gate_actionable_reason'] = row.get('actionable_reason')
        row['actionable_decision'] = 'WAIT'
        row['actionable_reason'] = gate['reason']
        row['analysis_ready'] = False
        row['setup_ready'] = False
        row['opportunity_state'] = 'WATCH'
        row['opportunity_state_reason'] = gate['reason']

        core = dict(row.get('primary_analysis') or {})
        core.update({
            'decision': 'WAIT',
            'analysis_ready': False,
            'setup_ready': False,
            'reason': gate['reason'],
            'setup_quality_gate': gate,
            'live_execution': False,
        })
        row['primary_analysis'] = core

        matrix = dict(row.get('timeframe_matrix') or {})
        core_matrix = dict(matrix.get('core_4_12h') or core)
        core_matrix.update(core)
        matrix['core_4_12h'] = core_matrix
        row['timeframe_matrix'] = matrix

        best = dict(row.get('best_available_action') or {})
        if best:
            best.update({
                'action': 'WAIT',
                'status': 'QUALITY_GATE_BLOCKED',
                'opportunity_state': 'WATCH',
                'can_execute': False,
                'analysis_only': True,
                'reason': gate['reason'],
            })
            row['best_available_action'] = best
        return row

    atlas.production_decision = build
    atlas.PRODUCT_QUALITY_GATE_STATE = {
        'enabled': True,
        'version': VERSION,
        'product_horizon': PRODUCT_HORIZON,
        'quarantined_setup_families': len(QUARANTINE),
        'score_threshold_unchanged': True,
        'raw_production_qualification_preserved': True,
        'analysis_only': True,
        'live_execution': False,
    }
    return atlas.PRODUCT_QUALITY_GATE_STATE
