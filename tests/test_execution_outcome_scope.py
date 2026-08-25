import execution_outcome_scope as eos


def record(direction='LONG', rr=1.5):
    if direction == 'LONG':
        g={'direction':'LONG','entry':100,'stop_loss':99,'tp1':101,'tp2':100+rr,'rr_tp2':rr}
    else:
        g={'direction':'SHORT','entry':100,'stop_loss':101,'tp1':99,'tp2':100-rr,'rr_tp2':rr}
    return {'geometry':g}


def test_valid_execution_geometry_passes():
    row={'production_signal_qualified':True,'direction':'LONG','id':'a'}
    out=eos.classify(row, record('LONG',1.5))
    assert out['execution_qualified'] is True


def test_rr_below_one_is_rejected_even_if_score_qualified():
    row={'production_signal_qualified':True,'direction':'LONG','id':'b'}
    out=eos.classify(row, record('LONG',0.5))
    assert out['execution_qualified'] is False
    assert 'RR_BELOW_ONE_TO_ONE' in out['reasons']
    assert 'INVALID_LONG_LEVEL_ORDER' in out['reasons']


def test_explicit_geometry_block_is_rejected():
    row={'production_signal_qualified':True,'direction':'LONG','execution_ready':False,'id':'c'}
    out=eos.classify(row, record('LONG',2.0))
    assert out['execution_qualified'] is False
    assert 'EXPLICIT_EXECUTION_NOT_READY' in out['reasons']


def test_short_ordering_is_enforced():
    row={'production_signal_qualified':True,'direction':'SHORT','id':'d'}
    good=eos.classify(row, record('SHORT',1.5))
    assert good['execution_qualified'] is True
    bad={'geometry':{'direction':'SHORT','entry':100,'stop_loss':101,'tp1':99,'tp2':99.5,'rr_tp2':1.5}}
    out=eos.classify(row,bad)
    assert out['execution_qualified'] is False
    assert 'INVALID_SHORT_LEVEL_ORDER' in out['reasons']


if __name__ == '__main__':
    test_valid_execution_geometry_passes()
    test_rr_below_one_is_rejected_even_if_score_qualified()
    test_explicit_geometry_block_is_rejected()
    test_short_ordering_is_enforced()
    print('execution outcome scope tests: ok')
