#!/usr/bin/env python3
import profitability_edge_intersection_shadow as p
x=p.build()
assert x['schema']=='ATLAS_EDGE_INTERSECTION_SHADOW_V2_DURABLE_COST_AWARE'
assert x['horizon']=='4-12H'
assert x['minimum_early_review_n']==10
assert x['minimum_promotion_n']==30
assert x['automatic_promotion'] is False
assert x['production_mutation_authorized'] is False
assert set(x['frozen_thresholds'])=={'score','relative_strength_adjustment','obstacle_adjustment'}
assert x['prospective_new_n']==len(x['prospective_observations'])
if not x['cost_and_funding_complete']:
    assert x['promotion_ready'] is False
if x['prospective_new_n'] < x['minimum_promotion_n']:
    assert x['promotion_ready'] is False
for o in x['prospective_observations']:
    assert p.ts(o['captured_at']) > p.ts(x['frozen_at'])
print('durable edge intersection prospective safety: PASS')
