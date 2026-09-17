import atlas_challenger_shadow as m


def row(epoch='HTF_SR_V2_2026-09-14', regime='4H_DIRECTIONAL_12H_NEUTRAL', blocker='HTF_CONFLICT', direction='LONG'):
    return {'epoch_id':epoch,'v2_regime':regime,'blocker_family':blocker,'direction':direction,'status':'MATURED','missed_opportunity':True,'horizons':{'4h':{'directional_return_pct':1.0,'mfe_pct':1.2,'mae_pct':0.4},'8h':{'directional_return_pct':1.5,'mfe_pct':2.0,'mae_pct':0.5},'12h':{'directional_return_pct':2.0,'mfe_pct':2.5,'mae_pct':0.6}}}


def test_only_post_v2_neutral_htf_conflict_is_eligible():
    assert m.eligible(row())
    assert not m.eligible(row(epoch='LEGACY_BASELINE'))
    assert not m.eligible(row(regime='NOT_CONDITIONAL_NEUTRAL_REGIME'))
    assert not m.eligible(row(blocker='SCORE_BELOW_THRESHOLD'))


def test_summary_is_directional_and_forward_only():
    rows=[row(direction='LONG'),row(direction='SHORT')]
    s=m.summarize(rows)
    assert s['matured_12h']==2
    assert s['mean_12h_directional_return_pct']==2.0
    assert s['by_direction']['LONG']['n']==1
    assert s['by_direction']['SHORT']['n']==1


def test_promotion_review_requires_real_sample():
    assert m.MIN_MATURED_FOR_PROMOTION_REVIEW >= 30


def test_contract_is_shadow_only():
    assert m.SCHEMA == 'ATLAS_CHALLENGER_SHADOW_V1'
