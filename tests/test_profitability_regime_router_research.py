#!/usr/bin/env python3
import profitability_regime_router_research as p
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_REGIME_ROUTER_RESEARCH_V1'
assert x['horizon']=='4-12H'
assert x['decision']=='RESEARCH_ONLY_NO_ROUTING_CHANGE'
assert x['production_mutation_authorized'] is False
assert x['automatic_promotion'] is False
assert x['causal_claim'] is False
assert x['chronological_discovery_n']+x['chronological_holdout_n']>0
for lane in x['lanes'].values():
    assert 'avg_mfe_r' in lane['discovery'] and 'avg_mae_r' in lane['holdout']
for o in x['expanding_walk_forward']['observations']:
    assert o['prior_lane_n'] >= 0
print('regime router research safety: PASS')
