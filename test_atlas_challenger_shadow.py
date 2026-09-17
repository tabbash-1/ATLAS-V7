import atlas_challenger_shadow as m


def row(epoch='HTF_SR_V2_2026-09-14',regime='4H_DIRECTIONAL_12H_NEUTRAL',blocker='HTF_CONFLICT',direction='LONG',ret=2.0):
    return {'epoch_id':epoch,'v2_regime':regime,'blocker_family':blocker,'direction':direction,'status':'MATURED','missed_opportunity':ret>0,'horizons':{'4h':{'directional_return_pct':ret/2,'mfe_pct':1.2,'mae_pct':0.4,'invalidation_hit':False},'8h':{'directional_return_pct':ret*.75,'mfe_pct':2.0,'mae_pct':0.5,'invalidation_hit':False},'12h':{'directional_return_pct':ret,'mfe_pct':2.5,'mae_pct':0.6,'invalidation_hit':False}}}


def test_eligibility_is_narrow():
    assert m.eligible(row())
    assert not m.eligible(row(epoch='LEGACY_BASELINE'))
    assert not m.eligible(row(regime='OTHER'))
    assert not m.eligible(row(blocker='SCORE_BELOW_THRESHOLD'))


def test_paired_actions_preserve_champion_wait():
    p=m.paired(row(direction='SHORT'))
    assert p['canonical_action']=='WAIT'
    assert p['shadow_action']=='SHORT'
    assert p['research_only'] is True and p['can_override_production'] is False and p['live_execution'] is False


def test_metrics_separate_direction_and_positive_rate():
    s=m.metrics([m.paired(row(direction='LONG',ret=2)),m.paired(row(direction='SHORT',ret=-1))])
    assert s['matured_12h']==2
    assert s['positive_12h_rate_pct']==50.0
    assert s['by_direction']['LONG']['positive_12h_rate_pct']==100.0
    assert s['by_direction']['SHORT']['positive_12h_rate_pct']==0.0


def test_partial_is_not_12h_matured():
    r=row(); r['status']='PARTIAL'; assert not m.mature12(r)


def test_promotion_review_is_not_authorization():
    assert m.MIN_MATURED_FOR_PROMOTION_REVIEW>=30
    assert m.SCHEMA=='ATLAS_CHALLENGER_SHADOW_V2_PAIRED_EVIDENCE'
