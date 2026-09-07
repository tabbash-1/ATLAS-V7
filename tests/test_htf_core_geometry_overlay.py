import types

from htf_core_geometry_overlay import build, install


def row(direction='LONG', entry_confirmation='LONG', alignment='ALIGNED'):
    px=100.0
    if direction=='LONG':
        pa4={'ok':True,'price':px,'atr14':2.0,'nearest_support_zone':{'low':96.0,'high':97.0,'mid':96.5},'nearest_resistance_zone':{'low':105.0,'high':106.0,'mid':105.5}}
        pa12={'ok':True,'price':px,'atr14':5.0,'nearest_support_zone':{'low':92.0,'high':94.0,'mid':93.0},'nearest_resistance_zone':{'low':111.0,'high':113.0,'mid':112.0}}
    else:
        pa4={'ok':True,'price':px,'atr14':2.0,'nearest_support_zone':{'low':94.0,'high':95.0,'mid':94.5},'nearest_resistance_zone':{'low':103.0,'high':104.0,'mid':103.5}}
        pa12={'ok':True,'price':px,'atr14':5.0,'nearest_support_zone':{'low':88.0,'high':90.0,'mid':89.0},'nearest_resistance_zone':{'low':108.0,'high':110.0,'mid':109.0}}
    return {
        'ok':True,'symbol':'BTCUSDT','score':76.0,'signal_threshold':68.0,
        'candidate_direction':entry_confirmation,'product_direction':direction,
        'entry_confirmation_direction':entry_confirmation,'direction_alignment':alignment,
        'production_signal_qualified':True,
        'actionable_decision':direction if alignment=='ALIGNED' else 'WAIT','actionable_reason':'EXECUTION_READY' if alignment=='ALIGNED' else 'ENTRY_CONFIRMATION_OPPOSES_PRODUCT_DIRECTION',
        'analysis_ready':alignment=='ALIGNED','setup_ready':alignment=='ALIGNED','execution_ready':False,
        'htf_thesis':{'status':'PASS','direction':direction,'product_direction':direction,'entry_confirmation_direction':entry_confirmation,'direction_alignment':alignment,'trigger':f'Confirm {direction}'},
        'htf_price_action':{'frames':{'4h':pa4,'12h':pa12}},
        'htf_scenario_engine':{'selected_case':None},
        'geometry_gate':{'status':'PASS','qualified':True,'reason':'RR_ONE_TO_ONE_OR_BETTER'},
        'trade_plan':{'direction':entry_confirmation,'entry':100.0,'stop_loss':98.0 if direction=='LONG' else 102.0,'tp1':102.0 if direction=='LONG' else 98.0,'tp2':104.0 if direction=='LONG' else 96.0,'geometry_provenance':{'geometry_version':'LEGACY_1H'}},
    }


def test_long_geometry_uses_htf_structure_and_rr():
    g=build(row('LONG'))
    assert g['status']=='READY' and g['ready'] is True
    assert g['product_direction']=='LONG'
    assert g['entry']==100.0
    assert g['stop_loss'] < 96.0
    assert g['tp1']==105.5
    assert g['tp2']==112.0
    assert g['rr_tp1'] >= 1.0
    assert g['geometry_provenance']['direction_authority']=='HTF_12H_4H'
    assert g['geometry_provenance']['stop_reference_timeframe']=='4h'
    assert g['geometry_provenance']['tp1_reference_timeframe']=='4h'
    assert g['score_changed'] is False and g['threshold_changed'] is False


def test_short_geometry_uses_htf_structure_and_rr():
    g=build(row('SHORT','SHORT'))
    assert g['status']=='READY' and g['ready'] is True
    assert g['product_direction']=='SHORT'
    assert g['stop_loss'] > 103.0
    assert g['tp1']==94.5
    assert g['tp2']==89.0
    assert g['rr_tp1'] >= 1.0


def test_opposed_one_hour_confirmation_withholds_geometry():
    g=build(row('LONG','SHORT','OPPOSED'))
    assert g['ready'] is False
    assert g['reason']=='ENTRY_CONFIRMATION_NOT_ALIGNED_WITH_HTF'
    assert g.get('entry') is None
    assert g['product_direction']=='LONG'
    assert g['entry_confirmation_direction']=='SHORT'


def test_insufficient_room_fails_closed():
    r=row('LONG')
    r['htf_price_action']['frames']['4h']['nearest_resistance_zone']={'low':100.5,'high':100.7,'mid':100.6}
    r['htf_price_action']['frames']['12h']['nearest_resistance_zone']={'low':101.0,'high':101.2,'mid':101.1}
    g=build(r)
    assert g['ready'] is False
    assert g['reason']=='INSUFFICIENT_HTF_ROOM_TO_TARGET'
    assert g['rr_tp1'] < 1.0


def test_install_promotes_only_aligned_htf_geometry_and_preserves_score_threshold():
    source=row('LONG')
    atlas=types.SimpleNamespace(production_decision=lambda symbol: dict(source))
    install(atlas)
    out=atlas.production_decision('BTCUSDT')
    assert out['htf_core_geometry']['ready'] is True
    assert out['trade_plan']['geometry_authority']=='HTF_4H_12H'
    assert out['trade_plan']['legacy_entry_geometry']['geometry_provenance']['geometry_version']=='LEGACY_1H'
    assert out['entry']==out['htf_core_geometry']['entry']
    assert out['score']==76.0 and out['signal_threshold']==68.0
    assert out['htf_core_geometry_score_preserved'] is True
    assert out['htf_core_geometry_threshold_preserved'] is True


def test_qualified_legacy_geometry_wait_is_cleared_by_ready_htf_geometry():
    source=row('LONG')
    source.update({'actionable_decision':'WAIT','actionable_reason':'RR_BELOW_ONE_TO_ONE','analysis_ready':False,'setup_ready':False})
    source['geometry_gate']={'status':'BLOCK','qualified':False,'reason':'RR_BELOW_ONE_TO_ONE'}
    atlas=types.SimpleNamespace(production_decision=lambda symbol: dict(source))
    install(atlas)
    out=atlas.production_decision('BTCUSDT')
    assert out['htf_core_geometry']['ready'] is True
    assert out['actionable_decision']=='LONG'
    assert out['actionable_reason']=='HTF_4_12H_GEOMETRY_READY_RAW_SCORE_QUALIFIED'
    assert out['legacy_geometry_blocker_cleared']=='RR_BELOW_ONE_TO_ONE'
    assert out['analysis_ready'] is True and out['setup_ready'] is True
    assert out['execution_ready'] is False
    assert out['htf_analysis_promotion_only'] is True


def test_consensus_wait_is_never_cleared_even_if_htf_geometry_is_ready():
    source=row('LONG')
    source.update({'actionable_decision':'WAIT','actionable_reason':'NO_DIRECTIONAL_CONSENSUS','analysis_ready':False,'setup_ready':False})
    atlas=types.SimpleNamespace(production_decision=lambda symbol: dict(source))
    install(atlas)
    out=atlas.production_decision('BTCUSDT')
    assert out['htf_core_geometry']['ready'] is True
    assert out['actionable_decision']=='WAIT'
    assert out['actionable_reason']=='NO_DIRECTIONAL_CONSENSUS'
    assert out.get('legacy_geometry_blocker_cleared') is None


def test_below_threshold_wait_is_never_cleared():
    source=row('LONG')
    source.update({'score':66.0,'production_signal_qualified':False,'actionable_decision':'WAIT','actionable_reason':'SCORE_BELOW_SIGNAL_THRESHOLD','analysis_ready':False,'setup_ready':False})
    source['geometry_gate']={'status':'BLOCK','qualified':False,'reason':'RR_BELOW_ONE_TO_ONE'}
    atlas=types.SimpleNamespace(production_decision=lambda symbol: dict(source))
    install(atlas)
    out=atlas.production_decision('BTCUSDT')
    assert out['htf_core_geometry']['ready'] is True
    assert out['actionable_decision']=='WAIT'
    assert out['actionable_reason']=='SCORE_BELOW_SIGNAL_THRESHOLD'
    assert out.get('legacy_geometry_blocker_cleared') is None
