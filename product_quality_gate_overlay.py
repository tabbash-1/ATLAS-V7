"""ATLAS final 4-12H product quality and presentation gate.

This overlay is the last authority over the user-facing analysis. It never
changes Production scores, the score threshold, or raw qualification. It may
fail closed to WAIT when a mature setup family is under evidence quarantine and
always emits one canonical analyst_output contract for the UI/API.
"""

VERSION = 'PRODUCT_QUALITY_GATE_V2_CANONICAL_ANALYST_OUTPUT'
PRODUCT_HORIZON = '4-12H'
PRODUCT_LANE = 'CORE_4_12H'

# Only mature, clearly adverse setup families are quarantined. We intentionally
# do not blacklist symbols or all LONG decisions: that would overfit the sample.
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
    evidence = QUARANTINE.get((direction, regime, playbook))
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


def _analyst_output(row, gate):
    decision = _norm(row.get('actionable_decision'))
    if decision not in ('LONG', 'SHORT'):
        decision = 'WAIT'
    plan = row.get('trade_plan') or {}
    actionable = decision in ('LONG', 'SHORT')
    reason = row.get('actionable_reason') or row.get('wait_reason') or gate.get('reason')
    reasons = []
    for item in (
        reason,
        f"PLAYBOOK_{_norm(row.get('playbook'))}" if row.get('playbook') else None,
        f"REGIME_{_norm(row.get('regime'))}" if row.get('regime') else None,
    ):
        if item and item not in reasons:
            reasons.append(item)

    if gate.get('status') == 'BLOCK':
        changes = list(gate.get('status_change_conditions') or [])
    elif decision == 'WAIT':
        changes = []
        trigger = plan.get('entry_trigger')
        if trigger:
            changes.append(trigger)
        if row.get('wait_reason'):
            changes.append(f"CLEAR_{row.get('wait_reason')}")
        if not changes:
            changes.append('NEW_VERIFIED_DIRECTIONAL_EVIDENCE_REQUIRED')
    else:
        changes = ['REASSESS_IF_INVALIDATION_OR_VERIFIED_DIRECTION_CHANGES']

    candidate_plan = {
        'direction': row.get('candidate_direction'),
        'entry': row.get('entry') if row.get('entry') is not None else plan.get('entry'),
        'stop_loss': row.get('stop_loss') if row.get('stop_loss') is not None else plan.get('stop_loss'),
        'take_profit': row.get('take_profit') if row.get('take_profit') is not None else plan.get('tp2'),
        'tp1': plan.get('tp1'),
        'risk_reward': row.get('risk_reward') if row.get('risk_reward') is not None else plan.get('rr_tp2'),
        'entry_trigger': plan.get('entry_trigger'),
        'invalidation': plan.get('invalidation') or 'Re-evaluate if verified structure or direction changes.',
    }

    return {
        'contract_version': VERSION,
        'symbol': row.get('symbol'),
        'lane': PRODUCT_LANE,
        'horizon': PRODUCT_HORIZON,
        'decision': decision,
        'analysis_ready': actionable,
        'confidence': row.get('score'),
        'confidence_basis': 'PRODUCTION_SCORE_NOT_PROBABILITY',
        'signal_threshold': row.get('signal_threshold'),
        'entry': candidate_plan['entry'] if actionable else None,
        'stop_loss': candidate_plan['stop_loss'] if actionable else None,
        'take_profit': candidate_plan['take_profit'] if actionable else None,
        'tp1': candidate_plan['tp1'] if actionable else None,
        'risk_reward': candidate_plan['risk_reward'] if actionable else None,
        'candidate_plan': candidate_plan,
        'reasons': reasons,
        'primary_reason': reason,
        'invalidation': candidate_plan['invalidation'],
        'what_changes_status': changes,
        'setup_quality_gate': gate,
        'production_qualified_raw': bool(row.get('production_signal_qualified')),
        'geometry_ready_raw': bool((row.get('geometry_gate') or {}).get('qualified')),
        'playbook': row.get('playbook'),
        'regime': row.get('regime'),
        'data_timestamp': row.get('generated_at') or row.get('generated_at_ms'),
        'data_degraded': bool(row.get('data_degraded', False)),
        'analysis_only': True,
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

        if gate.get('status') == 'BLOCK':
            # Preserve raw qualification for audit; only the canonical user-facing
            # 4-12H analysis is demoted. This avoids rewriting history or tuning
            # the score threshold to make results look better.
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

        row['analyst_output'] = _analyst_output(row, gate)
        row['canonical_product_decision'] = row['analyst_output']['decision']
        row['canonical_product_contract'] = 'analyst_output'
        return row

    atlas.production_decision = build
    atlas.PRODUCT_QUALITY_GATE_STATE = {
        'enabled': True,
        'version': VERSION,
        'product_lane': PRODUCT_LANE,
        'product_horizon': PRODUCT_HORIZON,
        'canonical_contract': 'analyst_output',
        'quarantined_setup_families': len(QUARANTINE),
        'score_threshold_unchanged': True,
        'raw_production_qualification_preserved': True,
        'analysis_only': True,
        'live_execution': False,
    }
    return atlas.PRODUCT_QUALITY_GATE_STATE
