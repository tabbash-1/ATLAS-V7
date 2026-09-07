"""ATLAS final 4-12H product quality and presentation gate.

This overlay is the last authority over the user-facing analysis. It never
changes Production scores, the score threshold, or raw qualification. It may
fail closed to WAIT only for mature setup families already under evidence
quarantine. Research/shadow findings that have not earned promotion are exposed
as warnings, never silently promoted into Production vetoes.
"""

from decision_intelligence import VERSION as DECISION_INTELLIGENCE_VERSION, build as build_decision_intelligence

# Keep the public contract identifier stable for existing API/CI consumers while
# exposing feature revisions separately.
VERSION = 'PRODUCT_QUALITY_GATE_V2_CANONICAL_ANALYST_OUTPUT'
FEATURE_VERSION = 'PRODUCT_QUALITY_GATE_FEATURE_V4_HTF_DIRECTION_GEOMETRY_CONTRACT'
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
        warnings.append({'code': 'DERIVATIVES_OPPOSE_DIRECTION', 'severity': 'MEDIUM', 'evidence_status': 'CONTEXT_NOT_VETO'})
    elif futures_available and futures_reason == 'ALIGNED':
        confirmations.append('DERIVATIVES_ALIGNED')
    elif not futures_available:
        warnings.append({'code': 'DERIVATIVES_NOT_VALIDATED_OR_UNAVAILABLE', 'severity': 'INFO', 'evidence_status': 'DATA_HEALTH'})

    rv = _num(row.get('relative_volume'))
    if rv is not None and rv >= 1.2:
        confirmations.append('RELATIVE_VOLUME_EXPANSION')

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


def _direction_state(row):
    thesis = dict(row.get('htf_thesis') or {})
    product_direction = row.get('product_direction') or thesis.get('product_direction') or thesis.get('direction')
    entry_direction = row.get('entry_confirmation_direction') or thesis.get('entry_confirmation_direction') or row.get('candidate_direction')
    alignment = row.get('direction_alignment') or thesis.get('direction_alignment')
    authority = row.get('direction_authority') or 'HTF_12H_4H'
    return {
        'product_direction': product_direction if product_direction in ('LONG', 'SHORT') else None,
        'entry_confirmation_direction': entry_direction if entry_direction in ('LONG', 'SHORT') else None,
        'alignment': alignment,
        'authority': authority,
        'authority_timeframes': list(thesis.get('authority_timeframes') or ['12h', '4h']),
        'entry_confirmation_timeframe': thesis.get('confirmation_timeframe') or '1h',
        'macro_context_timeframe': thesis.get('context_timeframe') or '1d',
        'macro_context_direction': thesis.get('daily_context'),
        'macro_context_confidence': thesis.get('daily_context_confidence'),
        'one_hour_can_flip_product_direction': False,
        'score_direction': row.get('candidate_direction'),
        'score_reused_for_opposite_direction': False,
    }


def _geometry_state(row):
    """Canonical geometry readiness: HTF geometry wins when installed.

    The legacy 1H-derived geometry gate remains visible for diagnostics and
    backward audit, but cannot contradict the final 4-12H analyst contract.
    """
    htf = dict(row.get('htf_core_geometry') or {})
    legacy = dict(row.get('geometry_gate') or {})
    if htf:
        ready = bool(htf.get('ready'))
        reason = htf.get('reason') or ('HTF_GEOMETRY_READY' if ready else 'HTF_GEOMETRY_NOT_READY')
        blockers = [] if ready else [reason]
        return {
            'ready': ready,
            'status': htf.get('status'),
            'reason': reason,
            'primary_blocker': None if ready else reason,
            'blocker_codes': blockers,
            'checks': {
                'product_direction_present': htf.get('product_direction') in ('LONG', 'SHORT'),
                'entry_confirmation_aligned': htf.get('direction_alignment') == 'ALIGNED',
                'rr_tp1_meets_minimum': bool(ready and _num(htf.get('rr_tp1')) is not None and _num(htf.get('rr_tp1')) >= _num(htf.get('min_rr'), 1.0)),
            },
            'reason_schema_version': 'HTF_CORE_GEOMETRY_REASON_V1',
            'geometry_version': htf.get('version'),
            'authority': 'HTF_4H_12H',
            'legacy_geometry_gate': legacy,
            'legacy_geometry_ready': bool(legacy.get('qualified')),
            'legacy_geometry_can_override': False,
        }
    legacy_blockers = list(legacy.get('blocker_codes') or [])
    if not legacy_blockers and not legacy.get('qualified') and legacy.get('reason'):
        legacy_blockers = [legacy.get('reason')]
    return {
        'ready': bool(legacy.get('qualified')),
        'status': legacy.get('status'),
        'reason': legacy.get('reason'),
        'primary_blocker': legacy.get('primary_blocker'),
        'blocker_codes': legacy_blockers,
        'checks': dict(legacy.get('checks') or {}),
        'reason_schema_version': legacy.get('reason_schema_version'),
        'geometry_version': legacy.get('version'),
        'authority': 'LEGACY_PRE_HTF',
        'legacy_geometry_gate': legacy,
        'legacy_geometry_ready': bool(legacy.get('qualified')),
        'legacy_geometry_can_override': True,
    }


def _analyst_output(row, gate):
    decision = _norm(row.get('actionable_decision'))
    if decision not in ('LONG', 'SHORT'):
        decision = 'WAIT'
    plan = row.get('trade_plan') or {}
    actionable = decision in ('LONG', 'SHORT')
    geometry_state = _geometry_state(row)
    geometry_blockers = list(geometry_state.get('blocker_codes') or [])
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

    for blocker in geometry_blockers:
        condition = f"CLEAR_GEOMETRY_{blocker}"
        if condition not in changes:
            changes.append(condition)

    direction_state = _direction_state(row)
    candidate_plan = {
        'direction': row.get('candidate_direction'),
        'direction_role': 'ENTRY_CONFIRMATION_AND_SCORE_GEOMETRY',
        'product_direction': direction_state['product_direction'],
        'direction_alignment': direction_state['alignment'],
        'entry': row.get('entry') if row.get('entry') is not None else plan.get('entry'),
        'stop_loss': row.get('stop_loss') if row.get('stop_loss') is not None else plan.get('stop_loss'),
        'take_profit': row.get('take_profit') if row.get('take_profit') is not None else plan.get('tp2'),
        'tp1': plan.get('tp1'),
        'risk_reward': row.get('risk_reward') if row.get('risk_reward') is not None else plan.get('rr_tp2'),
        'entry_trigger': plan.get('entry_trigger'),
        'invalidation': plan.get('invalidation') or 'Re-evaluate if verified structure or direction changes.',
        'geometry_provenance': plan.get('geometry_provenance') or {},
        'geometry_must_not_be_relabelled_to_opposite_product_direction': True,
    }
    profile = _evidence_profile(row, gate)

    return {
        'contract_version': VERSION,
        'feature_version': FEATURE_VERSION,
        'analysis_profile_version': PROFILE_VERSION,
        'symbol': row.get('symbol'),
        'lane': PRODUCT_LANE,
        'horizon': PRODUCT_HORIZON,
        'decision': decision,
        'product_direction': direction_state['product_direction'],
        'entry_confirmation_direction': direction_state['entry_confirmation_direction'],
        'direction_alignment': direction_state['alignment'],
        'direction_authority': direction_state['authority'],
        'direction_state': direction_state,
        'analysis_ready': actionable,
        'confidence': row.get('score'),
        'confidence_basis': 'PRODUCTION_SCORE_NOT_PROBABILITY',
        'confidence_direction': row.get('candidate_direction'),
        'signal_threshold': row.get('signal_threshold'),
        'entry': candidate_plan['entry'] if actionable else None,
        'stop_loss': candidate_plan['stop_loss'] if actionable else None,
        'take_profit': candidate_plan['take_profit'] if actionable else None,
        'tp1': candidate_plan['tp1'] if actionable else None,
        'risk_reward': candidate_plan['risk_reward'] if actionable else None,
        'candidate_plan': candidate_plan,
        'geometry_provenance': candidate_plan['geometry_provenance'] if actionable else {},
        'geometry_readiness': geometry_state,
        'evidence_profile': profile,
        'reasons': reasons,
        'primary_reason': reason,
        'invalidation': candidate_plan['invalidation'],
        'what_changes_status': changes,
        'setup_quality_gate': gate,
        'production_qualified_raw': bool(row.get('production_signal_qualified')),
        'geometry_ready_raw': bool(geometry_state.get('ready')),
        'geometry_ready_canonical': bool(geometry_state.get('ready')),
        'legacy_geometry_ready_raw': bool(geometry_state.get('legacy_geometry_ready')),
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
        row['quality_gate_feature_version'] = FEATURE_VERSION
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
        intelligence = build_decision_intelligence(row, row['analyst_output'])
        row['decision_intelligence'] = intelligence
        row['analyst_output']['decision_intelligence'] = intelligence
        row['evidence_profile'] = row['analyst_output']['evidence_profile']
        row['canonical_product_decision'] = row['analyst_output']['decision']
        row['canonical_product_direction'] = row['analyst_output']['product_direction']
        row['canonical_geometry_ready'] = row['analyst_output']['geometry_ready_canonical']
        row['canonical_geometry_authority'] = row['analyst_output']['geometry_readiness']['authority']
        row['canonical_product_contract'] = 'analyst_output'
        return row

    atlas.production_decision = build
    atlas.PRODUCT_QUALITY_GATE_STATE = {
        'enabled': True,'version': VERSION,'feature_version': FEATURE_VERSION,'analysis_profile_version': PROFILE_VERSION,
        'decision_intelligence_version': DECISION_INTELLIGENCE_VERSION,
        'product_lane': PRODUCT_LANE,'product_horizon': PRODUCT_HORIZON,
        'direction_authority': 'HTF_12H_4H','entry_confirmation_timeframe': '1h',
        'geometry_authority': 'HTF_4H_12H_WHEN_AVAILABLE',
        'canonical_contract': 'analyst_output','quarantined_setup_families': len(QUARANTINE),
        'score_threshold_unchanged': True,'raw_production_qualification_preserved': True,
        'score_never_relabelled_to_opposite_htf_direction': True,
        'legacy_geometry_cannot_override_htf_geometry': True,
        'decision_intelligence_shadow_only': True,'decision_intelligence_can_override': False,
        'research_warnings_never_auto_promote': True,'analysis_only': True,'live_execution': False,
    }
    return atlas.PRODUCT_QUALITY_GATE_STATE