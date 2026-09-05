"""ATLAS final 4-12H product quality and presentation gate.

This overlay is the last authority over the user-facing analysis. It never
changes Production scores, the score threshold, or raw qualification. It may
fail closed to WAIT only for mature setup families already under evidence
quarantine. Research/shadow findings that have not earned promotion are exposed
as warnings, never silently promoted into Production vetoes.
"""

VERSION = 'PRODUCT_QUALITY_GATE_V2_CANONICAL_ANALYST_OUTPUT'
PROFILE_VERSION = 'ATLAS_ANALYSIS_EVIDENCE_PROFILE_V1'
PRODUCT_HORIZON = '4-12H'
PRODUCT_LANE = 'CORE_4_12H'

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


def _num(value):
    try:
        return float(value)
    except Exception:
        return None


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


def _evidence_profile(row, gate):
    """Describe decision quality without changing the decision.

    Only already-promoted quarantine may BLOCK. Everything else here is a
    transparent risk/evidence annotation, including research candidates that
    explicitly failed or remain prospective-only.
    """
    direction = _norm(row.get('candidate_direction'))
    attr = row.get('score_attribution') or {}
    plan = row.get('trade_plan') or {}
    indicators = row.get('indicators') or {}
    warnings = []
    confirmations = []

    obstacle_reason = _norm(attr.get('obstacle_reason'))
    obstacle_pct = _num(attr.get('obstacle_distance_pct'))
    if direction == 'LONG' and obstacle_reason in ('CLOSE_PRIOR_STRUCTURE', 'VERY_CLOSE_PRIOR_STRUCTURE'):
        warnings.append({
            'code': 'LONG_CLOSE_PRIOR_STRUCTURE_SHADOW_RISK',
            'severity': 'HIGH' if obstacle_reason == 'VERY_CLOSE_PRIOR_STRUCTURE' else 'MEDIUM',
            'distance_pct': obstacle_pct,
            'evidence_status': 'PROSPECTIVE_SHADOW_ONLY_NOT_PRODUCTION_VETO',
            'source': 'status/long-close-structure-veto-shadow.json',
        })
    elif obstacle_reason in ('CLEAR_SPACE_TO_PRIOR_STRUCTURE', 'CONFIRMED_BREAKOUT_CLEAR_SPACE'):
        confirmations.append('STRUCTURAL_ROOM_CONFIRMED')

    futures_available = bool(row.get('futures_available'))
    futures_reason = _norm(attr.get('futures_reason'))
    if futures_available and futures_reason == 'OPPOSED':
        warnings.append({
            'code': 'DERIVATIVES_OPPOSE_DIRECTION',
            'severity': 'MEDIUM',
            'evidence_status': 'CONTEXT_NOT_VETO',
        })
    elif futures_available and futures_reason == 'ALIGNED':
        confirmations.append('DERIVATIVES_ALIGNED')
    elif not futures_available:
        warnings.append({
            'code': 'DERIVATIVES_NOT_VALIDATED_OR_UNAVAILABLE',
            'severity': 'INFO',
            'evidence_status': 'DATA_HEALTH',
        })

    rv = _num(row.get('relative_volume'))
    if rv is not None and rv >= 1.2:
        confirmations.append('RELATIVE_VOLUME_EXPANSION')
    # Volume-only promotion/demotion failed research gates, so never make it a veto.

    rsi = _num(indicators.get('rsi14') if indicators.get('rsi14') is not None else row.get('rsi14'))
    if rsi is not None and ((direction == 'LONG' and rsi >= 75) or (direction == 'SHORT' and rsi <= 25)):
        warnings.append({'code': 'MOMENTUM_EXTENSION_CONTEXT', 'severity': 'INFO', 'rsi14': round(rsi, 2), 'evidence_status': 'CONTEXT_NOT_VETO'})

    score = _num(row.get('score'))
    threshold = _num(row.get('signal_threshold'))
    margin = (score - threshold) if score is not None and threshold is not None else None
    if margin is not None and 0 <= margin <= 2:
        warnings.append({'code': 'MARGINAL_SCORE_CLEARANCE', 'severity': 'INFO', 'margin_points': round(margin, 2), 'evidence_status': 'CONTEXT_NOT_VETO'})

    if row.get('data_degraded'):
        warnings.append({'code': 'DATA_DEGRADED', 'severity': 'HIGH', 'evidence_status': 'DATA_HEALTH'})

    geometry = plan.get('geometry_provenance') or {}
    geometry_complete = all(geometry.get(k) is not None for k in ('geometry_version', 'entry_basis', 'stop_basis', 'tp1_basis', 'tp2_basis'))
    if geometry_complete:
        confirmations.append('GEOMETRY_PROVENANCE_COMPLETE')

    # Explicit record of rejected research prevents accidental future promotion.
    rejected_rules = [
        'LONG_ANTI_CHASE_VETO_REJECTED',
        'VOLUME_ONLY_RANKING_OR_DEMOTION_REJECTED',
        'NEUTRAL_RS_VETO_REJECTED',
    ]

    high = sum(1 for x in warnings if x.get('severity') == 'HIGH')
    med = sum(1 for x in warnings if x.get('severity') == 'MEDIUM')
    quality = 'CAUTION' if high or med >= 2 else 'NORMAL'
    if gate.get('status') == 'BLOCK':
        quality = 'BLOCKED'

    return {
        'version': PROFILE_VERSION,
        'quality': quality,
        'warnings': warnings,
        'confirmations': confirmations,
        'geometry_provenance': geometry,
        'research_rules_explicitly_not_promoted': rejected_rules,
        'only_quality_gate_can_change_canonical_decision': True,
        'score_changed': False,
        'threshold_changed': False,
        'analysis_only': True,
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
        'geometry_provenance': plan.get('geometry_provenance') or {},
    }
    profile = _evidence_profile(row, gate)

    return {
        'contract_version': VERSION,
        'analysis_profile_version': PROFILE_VERSION,
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
        'geometry_provenance': candidate_plan['geometry_provenance'] if actionable else {},
        'evidence_profile': profile,
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
        row['analysis_profile_version'] = PROFILE_VERSION
        row['production_score_preserved'] = True
        row['production_threshold_changed_by_quality_gate'] = False
        row['analysis_only'] = True
        row['live_execution'] = False

        if gate.get('status') == 'BLOCK':
            row['pre_quality_gate_actionable_decision'] = row.get('actionable_decision')
            row['pre_quality_gate_actionable_reason'] = row.get('actionable_reason')
            row['actionable_decision'] = 'WAIT'
            row['actionable_reason'] = gate['reason']
            row['analysis_ready'] = False
            row['setup_ready'] = False
            row['opportunity_state'] = 'WATCH'
            row['opportunity_state_reason'] = gate['reason']

            core = dict(row.get('primary_analysis') or {})
            core.update({'decision': 'WAIT','analysis_ready': False,'setup_ready': False,'reason': gate['reason'],'setup_quality_gate': gate,'live_execution': False})
            row['primary_analysis'] = core

            matrix = dict(row.get('timeframe_matrix') or {})
            core_matrix = dict(matrix.get('core_4_12h') or core)
            core_matrix.update(core)
            matrix['core_4_12h'] = core_matrix
            row['timeframe_matrix'] = matrix

            best = dict(row.get('best_available_action') or {})
            if best:
                best.update({'action': 'WAIT','status': 'QUALITY_GATE_BLOCKED','opportunity_state': 'WATCH','can_execute': False,'analysis_only': True,'reason': gate['reason']})
                row['best_available_action'] = best

        row['analyst_output'] = _analyst_output(row, gate)
        row['evidence_profile'] = row['analyst_output']['evidence_profile']
        row['canonical_product_decision'] = row['analyst_output']['decision']
        row['canonical_product_contract'] = 'analyst_output'
        return row

    atlas.production_decision = build
    atlas.PRODUCT_QUALITY_GATE_STATE = {
        'enabled': True,'version': VERSION,'analysis_profile_version': PROFILE_VERSION,
        'product_lane': PRODUCT_LANE,'product_horizon': PRODUCT_HORIZON,
        'canonical_contract': 'analyst_output','quarantined_setup_families': len(QUARANTINE),
        'score_threshold_unchanged': True,'raw_production_qualification_preserved': True,
        'research_warnings_never_auto_promote': True,'analysis_only': True,'live_execution': False,
    }
    return atlas.PRODUCT_QUALITY_GATE_STATE
