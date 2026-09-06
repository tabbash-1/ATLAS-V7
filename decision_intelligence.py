"""ATLAS Decision Intelligence V1.

A shadow-only reasoning layer over the canonical 4-12H analyst_output. It makes
opportunity formation, execution readiness and uncertainty explicit without
changing Production scores, thresholds, geometry qualification or LONG/SHORT/WAIT.

This layer is deliberately deterministic and inspectable. Learned/research
signals may be added as evidence only after independent chronological validation;
unvalidated model output must never become a hidden Production override.
"""
from __future__ import annotations

VERSION = 'ATLAS_DECISION_INTELLIGENCE_V1_SHADOW'
STAGES = ('NO_EDGE', 'WATCH', 'SETUP_FORMING', 'TRADE_READY')


def _num(value):
    try:
        return float(value)
    except Exception:
        return None


def _norm(value):
    return str(value or '').strip().upper()


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def _severity_weight(severity):
    return {'HIGH': 16.0, 'MEDIUM': 9.0, 'INFO': 3.0}.get(_norm(severity), 5.0)


def build(row, analyst_output):
    """Return an explainable shadow assessment; never mutate canonical inputs."""
    out = analyst_output or {}
    decision = _norm(out.get('decision'))
    candidate = _norm((out.get('candidate_plan') or {}).get('direction') or row.get('candidate_direction'))
    profile = out.get('evidence_profile') or {}
    geometry = out.get('geometry_readiness') or {}
    gate = out.get('setup_quality_gate') or row.get('setup_quality_gate') or {}
    warnings = list(profile.get('warnings') or [])
    confirmations = list(profile.get('confirmations') or [])

    score = _num(out.get('confidence'))
    threshold = _num(out.get('signal_threshold'))
    margin = score - threshold if score is not None and threshold is not None else None
    rr = _num(out.get('risk_reward'))
    if rr is None:
        rr = _num((out.get('candidate_plan') or {}).get('risk_reward'))

    hard_blockers = []
    soft_pressures = []
    positive_evidence = []

    if row.get('data_degraded') or out.get('data_degraded'):
        hard_blockers.append('DATA_DEGRADED')
    if gate.get('status') == 'BLOCK':
        hard_blockers.append(_norm(gate.get('reason')) or 'SETUP_QUALITY_GATE_BLOCKED')
    if geometry.get('ready') is not True:
        codes = list(geometry.get('blocker_codes') or [])
        hard_blockers.extend([f'GEOMETRY_{_norm(x)}' for x in codes] or ['GEOMETRY_NOT_READY'])

    for warning in warnings:
        code = _norm(warning.get('code')) or 'UNSPECIFIED_WARNING'
        if code == 'DATA_DEGRADED':
            if code not in hard_blockers:
                hard_blockers.append(code)
        else:
            soft_pressures.append({'code': code, 'severity': _norm(warning.get('severity')) or 'INFO'})

    for confirmation in confirmations:
        code = _norm(confirmation)
        if code and code not in positive_evidence:
            positive_evidence.append(code)

    # Evidence-strength score is not a probability and cannot replace Production score.
    # It summarizes how much independent context supports the current candidate.
    base_strength = 50.0
    if margin is not None:
        base_strength += _clamp(margin * 2.0, -24.0, 24.0)
    base_strength += min(18.0, len(positive_evidence) * 6.0)
    base_strength -= sum(_severity_weight(x.get('severity')) for x in soft_pressures)
    if gate.get('status') == 'BLOCK':
        base_strength -= 25.0
    evidence_strength = round(_clamp(base_strength), 1)

    checks = geometry.get('checks') or {}
    check_values = [v for v in checks.values() if isinstance(v, bool)]
    if geometry.get('ready') is True:
        execution_quality = 100.0
    elif check_values:
        execution_quality = round(100.0 * sum(1 for v in check_values if v) / len(check_values), 1)
    else:
        execution_quality = 0.0

    uncertainty = 18.0
    uncertainty += len(hard_blockers) * 18.0
    uncertainty += sum(_severity_weight(x.get('severity')) * 0.7 for x in soft_pressures)
    uncertainty -= min(18.0, len(positive_evidence) * 4.5)
    if margin is None:
        uncertainty += 12.0
    elif margin < 0:
        uncertainty += min(18.0, abs(margin) * 1.5)
    uncertainty = round(_clamp(uncertainty), 1)

    if decision in ('LONG', 'SHORT') and out.get('analysis_ready') is True and not hard_blockers:
        stage = 'TRADE_READY'
    elif candidate in ('LONG', 'SHORT') and geometry.get('ready') is True and margin is not None and margin >= -8:
        stage = 'SETUP_FORMING'
    elif candidate in ('LONG', 'SHORT') or margin is not None:
        stage = 'WATCH'
    else:
        stage = 'NO_EDGE'

    # A hard blocker may explain why a seemingly strong setup is still WAIT, but this
    # shadow classification never demotes/promotes the canonical decision itself.
    if hard_blockers and stage == 'TRADE_READY':
        stage = 'WATCH'

    if stage == 'TRADE_READY':
        next_requirement = 'MONITOR_INVALIDATION_AND_CANONICAL_GEOMETRY'
    elif hard_blockers:
        next_requirement = f'CLEAR_{hard_blockers[0]}'
    elif margin is not None and margin < 0:
        next_requirement = f'GAIN_{round(abs(margin), 1)}_PRODUCTION_SCORE_POINTS_WITH_VERIFIED_EVIDENCE'
    else:
        changes = list(out.get('what_changes_status') or [])
        next_requirement = changes[0] if changes else 'NEW_VERIFIED_DIRECTIONAL_EVIDENCE_REQUIRED'

    return {
        'version': VERSION,
        'mode': 'SHADOW_EXPLANATION_ONLY',
        'stage': stage,
        'candidate_direction': candidate if candidate in ('LONG', 'SHORT') else 'NONE',
        'canonical_decision': decision if decision in ('LONG', 'SHORT', 'WAIT') else 'WAIT',
        'evidence_strength': evidence_strength,
        'evidence_strength_basis': 'EXPLAINABLE_CONTEXT_INDEX_NOT_PROBABILITY',
        'execution_quality': execution_quality,
        'uncertainty': uncertainty,
        'score_margin': round(margin, 2) if margin is not None else None,
        'candidate_rr': round(rr, 3) if rr is not None else None,
        'hard_blockers': list(dict.fromkeys(hard_blockers)),
        'soft_pressures': soft_pressures,
        'positive_evidence': positive_evidence,
        'next_requirement': next_requirement,
        'promotion_status': 'SHADOW_ONLY_REQUIRES_CHRONOLOGICAL_HOLDOUT_AND_PROSPECTIVE_VALIDATION',
        'can_override_canonical_decision': False,
        'can_change_score': False,
        'can_change_threshold': False,
        'can_change_geometry': False,
        'analysis_only': True,
        'live_execution': False,
    }
