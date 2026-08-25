import execution_risk_management as erm


def test_long_geometry_uses_actual_support_and_resistance():
    g = erm.derive_structural_geometry({
        'entry': 100.0, 'direction': 'LONG',
        'support_distance_pct': 2.0, 'resistance_distance_pct': 4.0,
        'rr_tp2': 9.0,
    })
    assert g['stop_loss'] == 98.0
    assert g['tp1'] == 102.0
    assert g['tp2'] == 104.0
    assert g['rr_tp2'] == 2.0
    assert g['legacy_rr_input'] == 9.0
    assert g['method'] == 'STRUCTURAL_SUPPORT_RESISTANCE_ACTUAL_RR'


def test_short_geometry_is_symmetric():
    g = erm.derive_structural_geometry({
        'entry': 100.0, 'direction': 'SHORT',
        'support_distance_pct': 4.0, 'resistance_distance_pct': 2.0,
    })
    assert g['stop_loss'] == 102.0
    assert g['tp1'] == 98.0
    assert g['tp2'] == 96.0
    assert g['rr_tp2'] == 2.0


def test_geometry_blocks_sub_one_rr():
    assert erm.derive_structural_geometry({
        'entry': 100.0, 'direction': 'LONG',
        'support_distance_pct': 4.0, 'resistance_distance_pct': 2.0,
    }) is None


def test_valid_conditional_trade_plan_drives_management():
    p = erm._managed_plan_from_trade_plan({
        'status': 'CONDITIONAL', 'direction': 'LONG',
        'entry': 100.0, 'stop_loss': 98.0, 'tp1': 102.0, 'tp2': 104.0,
        'rr_tp2': 999.0,
    })
    assert p is not None
    assert p['source'] == 'TRADE_PLAN'
    assert p['status'] == 'CONDITIONAL_ARMED'
    assert p['entry'] == 100.0
    assert p['initial_stop_loss'] == 98.0
    assert p['tp1'] == 102.0
    assert p['tp2'] == 104.0
    assert p['after_tp1_stop'] == 100.0
    assert p['rr_tp2_actual'] == 2.0


def test_invalid_trade_plan_never_exposes_management_plan():
    assert erm._managed_plan_from_trade_plan({
        'status': 'CONDITIONAL', 'direction': 'LONG',
        'entry': 100.0, 'stop_loss': 98.0, 'tp1': 104.0, 'tp2': 103.0,
    }) is None
    assert erm._managed_plan_from_trade_plan({
        'status': 'CONDITIONAL', 'direction': 'LONG',
        'entry': 100.0, 'stop_loss': 96.0, 'tp1': 101.0, 'tp2': 102.0,
    }) is None


def test_tp1_then_old_stop_becomes_protected_win():
    managed = erm.manage_settlement_result({
        'path_outcome': 'LOSS', 'path_event': 'SL', 'r_multiple': -1.0,
        'terminal': True, 'tp1_reached': True, 'entry': 100.0,
    })
    assert managed['raw_unmanaged_path_outcome'] == 'LOSS'
    assert managed['raw_unmanaged_r_multiple'] == -1.0
    assert managed['path_outcome'] == 'WIN_TP1_PROTECTED'
    assert managed['r_multiple'] == 0.5
    assert managed['terminal'] is True


def test_stop_before_tp1_remains_full_loss():
    managed = erm.manage_settlement_result({
        'path_outcome': 'LOSS', 'path_event': 'SL', 'r_multiple': -1.0,
        'terminal': True, 'tp1_reached': False, 'entry': 100.0,
    })
    assert managed['path_outcome'] == 'LOSS'
    assert managed['r_multiple'] == -1.0


def test_tp2_is_blended_half_at_one_r_half_at_tp2():
    managed = erm.manage_settlement_result({
        'path_outcome': 'WIN_TP2', 'path_event': 'TP2', 'r_multiple': 2.0,
        'terminal': True, 'tp1_reached': True, 'entry': 100.0,
    })
    assert managed['r_multiple'] == 1.5


def test_managed_summary_keeps_unmanaged_fields_and_counts_positive_r():
    items = [
        erm.manage_settlement_result({'path_outcome': 'LOSS', 'r_multiple': -1.0, 'terminal': True, 'tp1_reached': True, 'entry': 100}),
        erm.manage_settlement_result({'path_outcome': 'LOSS', 'r_multiple': -1.0, 'terminal': True, 'tp1_reached': False, 'entry': 100}),
        erm.manage_settlement_result({'path_outcome': 'WIN_TP2', 'r_multiple': 2.0, 'terminal': True, 'tp1_reached': True, 'entry': 100}),
    ]
    summary = erm.summarize_managed_path(items, baseline_summary={'total': 3})
    assert summary['total'] == 3
    assert summary['wins'] == 2
    assert summary['losses'] == 1
    assert summary['net_r'] == 1.0
    assert summary['profit_factor_r'] == 2.0
    assert summary['protected_tp1_exits'] == 1


if __name__ == '__main__':
    test_long_geometry_uses_actual_support_and_resistance()
    test_short_geometry_is_symmetric()
    test_geometry_blocks_sub_one_rr()
    test_valid_conditional_trade_plan_drives_management()
    test_invalid_trade_plan_never_exposes_management_plan()
    test_tp1_then_old_stop_becomes_protected_win()
    test_stop_before_tp1_remains_full_loss()
    test_tp2_is_blended_half_at_one_r_half_at_tp2()
    test_managed_summary_keeps_unmanaged_fields_and_counts_positive_r()
    print('execution risk management tests: ok')
