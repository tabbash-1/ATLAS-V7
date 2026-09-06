"""Final Production response semantics guard.

Legacy Production decision code historically used ``execution_ready`` for
score-qualified + valid trade geometry. That is only geometry readiness, not an
entry trigger. This overlay runs after the decision/risk/quality layers and
makes the public contract explicit:

- geometry_ready: score + SL/TP geometry passed
- execution_permission_ready: canonical trade_plan.can_execute is explicitly true
- canonical_permission_ready: final analyst_output / setup quality gate permits entry
- execution_ready: all three are true

The final canonical quality decision is fail-closed: a quarantined/WAIT
``analyst_output`` can never be resurrected into LONG/SHORT by this HTTP layer.
This module does not change score, threshold, candidate direction, geometry, or
research policy.
"""

VERSION = 'PRODUCTION_EXECUTION_SEMANTICS_V2_CANONICAL_FAIL_CLOSED'


def install(atlas):
    original_json = atlas.Handler._json

    def guarded_json(self, payload, status=200):
        if isinstance(payload, dict) and payload.get('ok') is True and 'signal_qualified' in payload and 'candidate_direction' in payload and 'execution_ready' in payload:
            out = dict(payload)
            legacy_geometry_ready = bool(out.get('execution_ready'))
            plan = dict(out.get('trade_plan') or {})
            explicit_permission = plan.get('can_execute') is True

            analyst = out.get('analyst_output') if isinstance(out.get('analyst_output'), dict) else None
            quality_gate = out.get('setup_quality_gate') if isinstance(out.get('setup_quality_gate'), dict) else {}
            canonical_decision = str((analyst or {}).get('decision') or out.get('canonical_product_decision') or '').upper()
            canonical_contract_present = bool(analyst is not None or out.get('canonical_product_contract') == 'analyst_output')
            quality_blocked = str(quality_gate.get('status') or '').upper() == 'BLOCK'
            canonical_wait = canonical_contract_present and canonical_decision not in ('LONG', 'SHORT')
            canonical_permission = not quality_blocked and not canonical_wait

            permission_reason = 'CAN_EXECUTE_TRUE' if explicit_permission else 'CAN_EXECUTE_NOT_GRANTED'
            if quality_blocked:
                canonical_reason = quality_gate.get('reason') or (analyst or {}).get('primary_reason') or 'CANONICAL_QUALITY_GATE_BLOCKED'
            elif canonical_wait:
                canonical_reason = (analyst or {}).get('primary_reason') or out.get('actionable_reason') or 'CANONICAL_ANALYST_OUTPUT_WAIT'
            else:
                canonical_reason = 'CANONICAL_ENTRY_PERMITTED'

            out['geometry_ready'] = legacy_geometry_ready
            out['execution_permission_ready'] = explicit_permission
            out['execution_permission_source'] = 'canonical_trade_plan.can_execute'
            out['canonical_permission_ready'] = canonical_permission
            out['canonical_permission_source'] = 'analyst_output+setup_quality_gate'
            out['execution_semantics_version'] = VERSION
            out['execution_ready'] = bool(legacy_geometry_ready and explicit_permission and canonical_permission)

            direction = str(out.get('candidate_direction') or '').upper()
            if out['execution_ready'] and direction in ('LONG', 'SHORT'):
                out['actionable_decision'] = direction
                out['actionable_reason'] = 'EXECUTION_PERMISSION_GRANTED'
            else:
                out['actionable_decision'] = 'WAIT'
                if quality_blocked or canonical_wait:
                    out['actionable_reason'] = canonical_reason
                elif not out.get('signal_qualified'):
                    out['actionable_reason'] = out.get('wait_reason') or out.get('actionable_reason') or 'SIGNAL_NOT_QUALIFIED'
                elif not legacy_geometry_ready:
                    out['actionable_reason'] = out.get('geometry_gate', {}).get('reason') or 'GEOMETRY_NOT_READY'
                else:
                    out['actionable_reason'] = 'EXECUTION_TRIGGER_OR_PERMISSION_PENDING'

            out['execution_contract'] = {
                'score_qualified': bool(out.get('signal_qualified')),
                'geometry_ready': legacy_geometry_ready,
                'explicit_permission': explicit_permission,
                'permission_reason': permission_reason,
                'canonical_permission': canonical_permission,
                'canonical_reason': canonical_reason,
                'execution_ready': out['execution_ready'],
                'rule': 'signal_qualified AND geometry_ready AND canonical_trade_plan.can_execute=true AND canonical analyst_output permits entry',
            }
            payload = out
        return original_json(self, payload, status)

    atlas.Handler._json = guarded_json
    atlas.PRODUCTION_EXECUTION_SEMANTICS_VERSION = VERSION
    return {'version': VERSION, 'can_change_threshold': False, 'can_override_direction': False}
