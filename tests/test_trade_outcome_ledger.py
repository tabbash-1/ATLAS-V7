import trade_outcome_ledger as ledger


def canonical(direction='LONG', trade_ready=True, decision_id='dec-1'):
    return {
        'schema': 'ATLAS_CANONICAL_DECISION_TRUTH_V1',
        'decision_id': decision_id,
        'canonical_source_present': True,
        'source_of_truth': 'FINAL_TRADE_GATE',
        'decision': direction if trade_ready else 'WAIT',
        'direction': direction if trade_ready else None,
        'trade_ready': trade_ready,
        'paper_trade_eligible': trade_ready,
        'evaluation_horizons_h': [4, 8, 12],
    }


def row(**extra):
    base = {
        'id': 'x1',
        'captured_at': '2026-09-08T00:00:00+00:00',
        'captured_at_ms': 1000,
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100,
        'champion_take': True,
        'champion_score': 80,
        'final_score': 80,
        'signal_threshold': 68,
        'canonical_decision': canonical(),
        'forward_return_pct': {'4': 1.0, '8': 2.0, '12': -1.0},
    }
    base.update(extra)
    return base


def test_long_positive_is_win_and_negative_is_loss():
    assert ledger.classify_row(row(), 8)['outcome'] == 'WIN'
    assert ledger.classify_row(row(), 12)['outcome'] == 'LOSS'


def test_short_inverts_market_return():
    x = ledger.classify_row(row(direction='SHORT', canonical_decision=canonical('SHORT'), forward_return_pct={'8': -2.5}), 8)
    assert x['outcome'] == 'WIN'
    assert x['directional_return_pct'] == 2.5


def test_unmatured_is_open():
    x = ledger.classify_row(row(forward_return_pct={}), 12)
    assert x['outcome'] == 'OPEN'


def test_high_score_without_canonical_proof_is_not_production():
    x = row(canonical_decision=None, final_score=99, production_signal_qualified=True)
    assert ledger.is_production_signal(x) is False
    assert ledger.build_ledger([x], horizon=12, scope='signals') == []


def test_legacy_flag_without_final_gate_is_not_production():
    x = row(canonical_decision=None, production_signal_qualified=True, execution_ready=True)
    assert ledger.is_production_signal(x) is False
    legacy = ledger.build_ledger([x], horizon=12, scope='legacy_score_signals')
    assert len(legacy) == 1
    assert legacy[0]['production_signal_qualified'] is False
    assert legacy[0]['legacy_score_signal'] is True


def test_canonical_wait_is_not_production_even_with_high_score():
    x = row(canonical_decision=canonical(trade_ready=False), final_score=100, production_signal_qualified=True)
    assert ledger.is_production_signal(x) is False


def test_canonical_trade_ready_requires_decision_id_and_final_gate_source():
    good = row(canonical_decision=canonical('LONG', True, 'abc123'))
    missing_id = row(canonical_decision=canonical('LONG', True, ''))
    wrong_source = row(canonical_decision={**canonical(), 'source_of_truth': 'ANALYST_OUTPUT'})
    assert ledger.is_production_signal(good) is True
    assert ledger.is_production_signal(missing_id) is False
    assert ledger.is_production_signal(wrong_source) is False


def test_official_horizons_are_only_4_8_12():
    assert ledger.HORIZONS == (4, 8, 12)
    for h in (4, 8, 12):
        ledger.classify_row(row(), h)
    for h in (1, 24):
        try:
            ledger.classify_row(row(), h)
        except ValueError:
            pass
        else:
            raise AssertionError(f'legacy horizon {h} must be rejected by official ledger')


def test_signal_scope_is_final_gate_not_research_champion():
    rows = [
        row(id='production', canonical_decision=canonical('LONG', True, 'p1')),
        row(id='legacy', captured_at_ms=1100, canonical_decision=None, final_score=90, production_signal_qualified=True),
        row(id='research', captured_at_ms=1200, canonical_decision=None, final_score=55, champion_take=True),
    ]
    signals = ledger.build_ledger(rows, horizon=12, scope='signals')
    legacy = ledger.build_ledger(rows, horizon=12, scope='legacy_score_signals')
    assert [x['id'] for x in signals] == ['production']
    assert {x['id'] for x in legacy} == {'legacy'}


def test_summary_win_rate_uses_decisive_closed_only():
    rows = [
        row(id='w', canonical_decision=canonical('LONG', True, 'w'), forward_return_pct={'12': 2}),
        row(id='l', captured_at_ms=1100, canonical_decision=canonical('LONG', True, 'l'), forward_return_pct={'12': -1}),
        row(id='o', captured_at_ms=1200, canonical_decision=canonical('LONG', True, 'o'), forward_return_pct={}),
    ]
    s = ledger.summarize(rows, 12, 'signals')
    assert s['overall']['wins'] == 1
    assert s['overall']['losses'] == 1
    assert s['overall']['open'] == 1
    assert s['overall']['win_rate_pct'] == 50.0
    assert s['canonical_source_of_truth'] == 'FINAL_TRADE_GATE'
    assert s['legacy_backfill_allowed'] is False


def test_version_provenance_is_preserved_without_inference():
    x = ledger.classify_row(row(
        scoring_version='PROD_SIGNAL_V6',
        decision_version='DECISION_V3',
        trade_plan_version='PLAN_V2',
        policy_version='POLICY_V1',
        generation_id='gen-20260908-001',
    ), 12)
    assert x['scoring_version'] == 'PROD_SIGNAL_V6'
    assert x['decision_version'] == 'DECISION_V3'
    assert x['trade_plan_version'] == 'PLAN_V2'
    assert x['policy_version'] == 'POLICY_V1'
    assert x['generation_id'] == 'gen-20260908-001'


if __name__ == '__main__':
    test_long_positive_is_win_and_negative_is_loss()
    test_short_inverts_market_return()
    test_unmatured_is_open()
    test_high_score_without_canonical_proof_is_not_production()
    test_legacy_flag_without_final_gate_is_not_production()
    test_canonical_wait_is_not_production_even_with_high_score()
    test_canonical_trade_ready_requires_decision_id_and_final_gate_source()
    test_official_horizons_are_only_4_8_12()
    test_signal_scope_is_final_gate_not_research_champion()
    test_summary_win_rate_uses_decisive_closed_only()
    test_version_provenance_is_preserved_without_inference()
    print('trade outcome ledger tests: ok')
