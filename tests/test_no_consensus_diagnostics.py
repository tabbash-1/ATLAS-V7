import no_consensus_diagnostics as n


def row(change=2.0, price=101.0, ema20=100.0, ema50=102.0, rsi=55.0, mom=-1.0):
    return {
        'reason':'NO_DIRECTIONAL_CONSENSUS','candidate_direction':'NONE','wait_price':price,
        'decision_context':{
            'direction_votes_long':2,'direction_votes_short':2,
            'ema20':ema20,'ema50':ema50,'rsi14':rsi,'momentum_24h_pct':mom,
        },
        'horizons':{f'{h}h':{'change_pct':change} for h in (1,3,6,12,24)},
    }


def test_signature_reconstructs_exact_four_votes():
    r=row()
    assert n.tie_signature(r)=='P>L|E<S|R>L|M<S'


def test_non_two_two_is_excluded():
    r=row(); r['decision_context']['direction_votes_long']=1; r['decision_context']['direction_votes_short']=3
    assert n.is_two_two(r) is False


def test_missing_context_is_reported_not_invented():
    r={'reason':'NO_DIRECTIONAL_CONSENSUS','wait_price':100,'decision_context':{},'horizons':{}}
    out=n.diagnose({'records':[r]})
    assert out['no_consensus_records']==1
    assert out['contextual_two_two_records']==0
    assert out['shadow_hypotheses']==[]


def test_small_sample_never_breaks_tie():
    out=n.diagnose({'records':[row(change=2.0) for _ in range(10)]})
    assert out['shadow_hypotheses']==[]
    assert out['safety']['production_tie_breaking_enabled'] is False


def test_repeated_bias_can_only_create_shadow_hypothesis():
    out=n.diagnose({'records':[row(change=2.0) for _ in range(20)]})
    assert len(out['shadow_hypotheses'])==1
    h=out['shadow_hypotheses'][0]
    assert h['direction']=='UP'
    assert h['production_applied'] is False
    assert out['safety']['threshold_changed'] is False
    assert out['safety']['can_execute'] is False


def test_conflicting_horizon_directions_are_not_eligible():
    rows=[]
    for _ in range(20):
        r=row(change=2.0)
        r['horizons']['1h']['change_pct']=2.0
        r['horizons']['3h']['change_pct']=-2.0
        r['horizons']['6h']['change_pct']=0.2
        r['horizons']['12h']['change_pct']=0.2
        r['horizons']['24h']['change_pct']=0.2
        rows.append(r)
    out=n.diagnose({'records':rows})
    assert out['shadow_hypotheses']==[]


if __name__=='__main__':
    test_signature_reconstructs_exact_four_votes()
    test_non_two_two_is_excluded()
    test_missing_context_is_reported_not_invented()
    test_small_sample_never_breaks_tie()
    test_repeated_bias_can_only_create_shadow_hypothesis()
    test_conflicting_horizon_directions_are_not_eligible()
    print('no consensus diagnostics tests: ok')
