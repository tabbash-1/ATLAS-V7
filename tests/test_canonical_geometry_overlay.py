from canonical_geometry_overlay import REASON_SCHEMA_VERSION, VERSION, assess


def test_long_geometry_recomputes_rr_from_exact_levels():
    g = assess('LONG', 100.0, 98.0, 104.0)
    assert g['status'] == 'PASS'
    assert g['qualified'] is True
    assert g['risk_reward'] == 2.0
    assert g['rr_source'] == 'RECOMPUTED_FROM_EXACT_ENTRY_STOP_TARGET'
    assert g['version'] == VERSION
    assert g['reason_schema_version'] == REASON_SCHEMA_VERSION
    assert g['blocker_codes'] == []
    assert g['checks']['rr_meets_minimum'] is True


def test_short_geometry_recomputes_rr_from_exact_levels():
    g = assess('SHORT', 100.0, 102.0, 96.0)
    assert g['status'] == 'PASS'
    assert g['qualified'] is True
    assert g['risk_reward'] == 2.0


def test_geometry_blocks_rr_below_one_with_exact_code():
    g = assess('LONG', 100.0, 98.0, 101.0)
    assert g['status'] == 'BLOCK'
    assert g['qualified'] is False
    assert g['reason'] == 'RR_BELOW_ONE_TO_ONE'
    assert g['primary_blocker'] == 'RR_BELOW_MINIMUM'
    assert g['blocker_codes'] == ['RR_BELOW_MINIMUM']
    assert g['risk_reward'] == 0.5
    assert g['checks']['rr_meets_minimum'] is False


def test_geometry_blocks_invalid_stop_side_with_exact_code():
    g = assess('LONG', 100.0, 101.0, 104.0)
    assert g['status'] == 'BLOCK'
    assert g['qualified'] is False
    assert g['reason'] == 'INVALID_ENTRY_SL_TP_ORDER'
    assert g['blocker_codes'] == ['STOP_WRONG_SIDE']
    assert g['checks']['stop_correct_side'] is False
    assert g['checks']['target_correct_side'] is True


def test_geometry_reports_each_missing_level():
    g = assess('LONG', None, None, 104.0)
    assert g['reason'] == 'GEOMETRY_INCOMPLETE'
    assert g['primary_blocker'] == 'MISSING_ENTRY'
    assert g['blocker_codes'] == ['MISSING_ENTRY', 'MISSING_STOP']
    assert g['reason_schema_version'] == REASON_SCHEMA_VERSION


def test_geometry_never_uses_external_rr():
    # Regression for the HYPE-style bug: displayed levels imply 2R, so a stale
    # scorer rr value must have no way to downgrade this geometry assessment.
    g = assess('LONG', 10.0, 9.5, 11.0)
    assert g['qualified'] is True
    assert g['risk_reward'] == 2.0
