"""Overlay horizon-fit classification on the final ATLAS production decision.

The wrapped Production decision remains authoritative. This module only narrows
the Quick shadow lane and adds an explicit 12-24h Swing research lane.
"""

import horizon_fit_policy

VERSION = 'HORIZON_FIT_OVERLAY_V7_PROVISIONAL_EPISODE_QUALITY'


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
        score_attr = row.get('score_attribution') or {}

        fit = horizon_fit_policy.classify(
            symbol=row.get('symbol') or symbol,
            direction=row.get('candidate_direction'),
            score=row.get('score'),
            threshold=row.get('signal_threshold'),
            votes=row.get('direction_votes'),
            relative_volume=row.get('relative_volume'),
            tactical_rr=tactical.get('risk_reward'),
            breakout_confirmed=bool(breakout.get('confirmed')),
            production_qualified=bool(row.get('production_signal_qualified')),
            execution_ready=bool(row.get('execution_ready')),
            obstacle_reason=score_attr.get('obstacle_reason'),
        )

        existing_quick = row.get('quick_trade_shadow') or {}
        guard = getattr(atlas, 'QUICK_REENTRY_GUARD', None)
        strict_quick_allowed = fit['quick'].get('status') == 'QUICK_TRADE_SHADOW'
        guard_cleanup = None
        guard_approval = None

        if existing_quick.get('status') == 'QUICK_TRADE_SHADOW' and guard is not None:
            if strict_quick_allowed and hasattr(guard, 'approve_active_policy'):
                guard_approval = guard.approve_active_policy(
                    row.get('symbol') or symbol,
                    row.get('candidate_direction'),
                    horizon_fit_policy.VERSION,
                )
            elif not strict_quick_allowed and hasattr(guard, 'cancel_active'):
                guard_cleanup = guard.cancel_active(
                    row.get('symbol') or symbol,
                    row.get('candidate_direction'),
                    reason='HORIZON_FIT_STRICT_QUICK_REJECTED',
                )

        legacy_active_rejected = False
        if existing_quick.get('status') == 'QUICK_TRADE_ACTIVE' and guard is not None and hasattr(guard, 'reject_legacy_active'):
            guard_cleanup = guard.reject_legacy_active(
                row.get('symbol') or symbol,
                existing_quick.get('direction') or row.get('candidate_direction'),
                horizon_fit_policy.VERSION,
                reason='LEGACY_QUICK_ACTIVE_PREDATES_HORIZON_FIT',
            )
            legacy_active_rejected = bool((guard_cleanup or {}).get('cancelled'))

        preserve_guard_state = (
            existing_quick.get('reason') == 'POST_STOP_REENTRY_COOLDOWN' or
            (existing_quick.get('status') == 'QUICK_TRADE_ACTIVE' and not legacy_active_rejected)
        )
        if preserve_guard_state:
            strict_quick = dict(existing_quick)
            strict_quick['policy_version'] = horizon_fit_policy.VERSION
            strict_quick['evaluation_horizons'] = ['1h', '3h']
        elif strict_quick_allowed and existing_quick.get('status') == 'QUICK_TRADE_SHADOW':
            strict_quick = dict(existing_quick)
            strict_quick.update(fit['quick'])
            strict_quick['policy_version'] = horizon_fit_policy.VERSION
        else:
            strict_quick = dict(fit['quick'])
            strict_quick['policy_version'] = horizon_fit_policy.VERSION

        if guard_cleanup is not None:
            strict_quick['legacy_guard_cleanup'] = guard_cleanup
        if guard_approval is not None:
            strict_quick['guard_policy_approval'] = guard_approval

        swing = dict(matrix.get('swing') or {})
        swing.update(fit['swing'])
        swing['opportunity_state'] = row.get('opportunity_state')
        swing['risk_reward'] = row.get('risk_reward')
        swing['actionable_decision'] = row.get('actionable_decision')

        matrix['quick_1_3h'] = strict_quick
        matrix.pop('quick_1_2h', None)
        matrix['swing_12_24h'] = swing
        matrix['swing'] = swing

        row['quick_trade_shadow'] = strict_quick
        row['swing_research'] = swing
        row['swing_quality_tier'] = swing.get('swing_quality_tier')
        row['swing_quality_evidence'] = swing.get('swing_quality_evidence')
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
        'legacy_quick_guard_cleanup': True,
        'legacy_active_state_migration': True,
        'clean_watch_state': True,
        'combo_calibrated_swing_quality': True,
        'independent_episode_validation_required': True,
        'quality_labels_provisional': True,
    }
    return atlas.HORIZON_FIT_STATE
