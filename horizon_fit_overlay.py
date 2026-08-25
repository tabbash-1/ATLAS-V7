"""Overlay horizon-fit classification on the final ATLAS production decision.

The wrapped Production decision remains authoritative. This module only narrows
the Quick shadow lane and adds an explicit 12-24h Swing research lane.
"""

import horizon_fit_policy

VERSION = 'HORIZON_FIT_OVERLAY_V1'


def install(atlas):
    original = atlas.production_decision

    def build(symbol):
        result = original(symbol)
        if not isinstance(result, dict) or not result.get('ok'):
            return result

        row = result
        matrix = row.get('timeframe_matrix') or {}
        tactical = row.get('tactical_opportunity') or matrix.get('tactical_1_3h') or {}
        structural = row.get('structural_geometry') or {}
        breakout = structural.get('breakout') or {}

        fit = horizon_fit_policy.classify(
            direction=row.get('candidate_direction'),
            score=row.get('score'),
            threshold=row.get('signal_threshold'),
            votes=row.get('direction_votes'),
            relative_volume=row.get('relative_volume'),
            tactical_rr=tactical.get('risk_reward'),
            breakout_confirmed=bool(breakout.get('confirmed')),
            production_qualified=bool(row.get('production_signal_qualified')),
            execution_ready=bool(row.get('execution_ready')),
        )

        # Preserve active/cooldown guard states; otherwise apply stricter Quick lane.
        existing_quick = row.get('quick_trade_shadow') or {}
        if existing_quick.get('status') in ('QUICK_TRADE_ACTIVE',) or existing_quick.get('reason') == 'POST_STOP_REENTRY_COOLDOWN':
            strict_quick = dict(existing_quick)
            strict_quick['policy_version'] = horizon_fit_policy.VERSION
            strict_quick['evaluation_horizons'] = ['1h', '3h']
        else:
            strict_quick = dict(existing_quick)
            strict_quick.update(fit['quick'])
            strict_quick['policy_version'] = horizon_fit_policy.VERSION

        swing = dict(matrix.get('swing') or {})
        swing.update(fit['swing'])
        swing['opportunity_state'] = row.get('opportunity_state')
        swing['risk_reward'] = row.get('risk_reward')
        swing['actionable_decision'] = row.get('actionable_decision')

        matrix['quick_1_3h'] = strict_quick
        matrix.pop('quick_1_2h', None)
        matrix['swing_12_24h'] = swing
        matrix['swing'] = swing  # compatibility alias

        row['quick_trade_shadow'] = strict_quick
        row['swing_research'] = swing
        row['horizon_fit'] = fit
        row['preferred_horizon'] = fit['preferred_horizon']
        row['timeframe_matrix'] = matrix
        row['horizon_policy_version'] = horizon_fit_policy.VERSION
        row['production_threshold_changed_by_horizon_policy'] = False
        row['horizon_fit_overlay_version'] = VERSION
        return row

    atlas.production_decision = build
    atlas.HORIZON_FIT_STATE = {
        'enabled': True,
        'version': VERSION,
        'policy_version': horizon_fit_policy.VERSION,
        'quick_horizon': '1-3H',
        'swing_horizon': '12-24H',
        'production_threshold_unchanged': True,
        'production_override_allowed': False,
    }
    return atlas.HORIZON_FIT_STATE
