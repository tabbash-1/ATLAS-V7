#!/usr/bin/env python3
import profitability_regime_router_research as p
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_NATIVE_REGIME_ROUTER_V2'
assert x['horizon']=='4-12H'
assert x['decision']=='RESEARCH_ONLY_NO_ROUTING_CHANGE'
assert x['production_mutation_authorized'] is False
assert x['automatic_promotion'] is False
assert x['causal_claim'] is False
assert x['chronological_discovery_n']+x['chronological_holdout_n']>0
# Direction-specific native trend regimes must never be pooled.
assert not ('TREND_CONTINUATION' in x['lanes'])
if 'TREND_UP' in x['lanes'] and 'TREND_DOWN' in x['lanes']:
    assert x['lanes']['TREND_UP'] is not x['lanes']['TREND_DOWN']
for lane in x['lanes'].values():
    assert lane['descriptive_only'] is True
    assert 'avg_mfe_r' in lane['discovery'] and 'avg_mae_r' in lane['holdout']
for o in x['expanding_walk_forward']['observations']:
    assert o['prior_lane_n'] >= 0
assert x['router_candidate_ready'] is False or x['expanding_walk_forward']['admitted']['n']>=10
print('native regime router research safety: PASS')
