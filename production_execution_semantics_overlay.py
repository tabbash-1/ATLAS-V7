"""Final Production response semantics guard.

Legacy Production decision code historically used ``execution_ready`` for
score-qualified + valid trade geometry. That is only geometry readiness, not an
entry trigger. This overlay runs after the decision/risk layers and makes the
public contract explicit:

- geometry_ready: score + SL/TP geometry passed
- execution_permission_ready: canonical trade_plan.can_execute is explicitly true
- execution_ready: both are true

It does not change score, threshold, direction, geometry, or research policy.
"""

VERSION = 'PRODUCTION_EXECUTION_SEMANTICS_V1_EXPLICIT_PERMISSION'


def install(atlas):
    original_json = atlas.Handler._json

    def guarded_json(self, payload, status=200):
        if isinstance(payload, dict) and payload.get('ok') is True and 'signal_qualified' in payload and 'candidate_direction' in payload and 'execution_ready' in payload:
            out = dict(payload)
            legacy_geometry_ready = bool(out.get('execution_ready'))
            plan = dict(out.get('trade_plan') or {})
            explicit_permission = plan.get('can_execute') is True
            permission_reason = 'CAN_EXECUTE_TRUE' if explicit_permission else 'CAN_EXECUTE_NOT_GRANTED'

            out['geometry_ready'] = legacy_geometry_ready
            out['execution_permission_ready'] = explicit_permission
            out['execution_permission_source'] = 'canonical_trade_plan.can_execute'
            out['execution_semantics_version'] = VERSION
            out['execution_ready'] = bool(legacy_geometry_ready and explicit_permission)

            direction = str(out.get('candidate_direction') or '').upper()
            if out['execution_ready'] and direction in ('LONG', 'SHORT'):
                out['actionable_decision'] = direction
                out['actionable_reason'] = 'EXECUTION_PERMISSION_GRANTED'
            else:
                out['actionable_decision'] = 'WAIT'
                if not out.get('signal_qualified'):
                    # Preserve the original qualification reason where possible.
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
                'execution_ready': out['execution_ready'],
                'rule': 'signal_qualified AND geometry_ready AND canonical_trade_plan.can_execute=true',
            }
            payload = out
        return original_json(self, payload, status)

    atlas.Handler._json = guarded_json
    atlas.PRODUCTION_EXECUTION_SEMANTICS_VERSION = VERSION
    return {'version': VERSION, 'can_change_threshold': False, 'can_override_direction': False}
