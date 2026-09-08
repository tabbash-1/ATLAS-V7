import execution_outcome_scope as eos


def canonical(direction='LONG', ready=True):
    return {
        'schema':'ATLAS_CANONICAL_DECISION_TRUTH_V1',
        'source_of_truth':'FINAL_TRADE_GATE',
        'canonical_source_present':True,
        'decision_id':f'decision-{direction.lower()}',
        'decision':direction if ready else 'WAIT',
        'direction':direction if ready else None,
        'trade_ready':ready,
        'paper_trade_eligible':ready,
        'evaluation_horizons_h':[4,8,12],
    }


def row(direction='LONG', ready=True, **extra):
    out={
        'id':'x', 'direction':direction,
        'canonical_decision':canonical(direction,ready),
        'canonical_decision_id':f'decision-{direction.lower()}',
        # A legacy flag may coexist but is never the authority.
        'production_signal_qualified':True,
    }
    out.update(extra)
    return out


def record(direction='LONG', rr=1.5):
    if direction == 'LONG':
        g={'direction':'LONG','entry':100,'stop_loss':99,'tp1':101,'tp2':100+rr,'rr_tp2':rr}
    else:
        g={'direction':'SHORT','entry':100,'stop_loss':101,'tp1':99,'tp2':100-rr,'rr_tp2':rr}
    return {'geometry':g}


def test_valid_canonical_execution_geometry_passes():
    out=eos.classify(row('LONG'), record('LONG',1.5))
    assert out['execution_qualified'] is True
    assert out['canonical_trade_ready'] is True
    assert out['decision_source_of_truth']=='FINAL_TRADE_GATE'


def test_legacy_flag_cannot_create_execution_trade():
    legacy={'production_signal_qualified':True,'direction':'LONG','id':'legacy'}
    out=eos.classify(legacy, record('LONG',1.5))
    assert out['execution_qualified'] is False
    assert out['canonical_trade_ready'] is False
    assert 'NOT_CANONICAL_TRADE_READY' in out['reasons']


def test_rr_below_one_is_rejected_even_if_canonical_trade_ready():
    out=eos.classify(row('LONG'), record('LONG',0.5))
    assert out['execution_qualified'] is False
    assert 'RR_BELOW_ONE_TO_ONE' in out['reasons']
    assert 'INVALID_LONG_LEVEL_ORDER' in out['reasons']


def test_explicit_geometry_block_is_rejected():
    out=eos.classify(row('LONG', execution_ready=False), record('LONG',2.0))
    assert out['execution_qualified'] is False
    assert 'EXPLICIT_EXECUTION_NOT_READY' in out['reasons']


def test_short_ordering_is_enforced():
    good=eos.classify(row('SHORT'), record('SHORT',1.5))
    assert good['execution_qualified'] is True
    bad={'geometry':{'direction':'SHORT','entry':100,'stop_loss':101,'tp1':99,'tp2':99.5,'rr_tp2':1.5}}
    out=eos.classify(row('SHORT'),bad)
    assert out['execution_qualified'] is False
    assert 'INVALID_SHORT_LEVEL_ORDER' in out['reasons']


if __name__ == '__main__':
    test_valid_canonical_execution_geometry_passes()
    test_legacy_flag_cannot_create_execution_trade()
    test_rr_below_one_is_rejected_even_if_canonical_trade_ready()
    test_explicit_geometry_block_is_rejected()
    test_short_ordering_is_enforced()
    print('execution outcome scope tests: ok')
