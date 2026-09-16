#!/usr/bin/env python3
import profitability_edge_intersection_shadow as p
x=p.build()
assert x['schema']=='ATLAS_EDGE_INTERSECTION_SHADOW_V1'
assert x['horizon']=='4-12H'
assert x['prospective_new_n']==0
assert x['promotion_ready'] is False
assert x['automatic_promotion'] is False
assert x['production_mutation_authorized'] is False
assert x['decision']=='FREEZE_AND_COLLECT_PROSPECTIVE_EVIDENCE'
assert x['prospective_cost_adjusted_required'] is True
assert set(x['frozen_thresholds'])=={'score','relative_strength_adjustment','obstacle_adjustment'}
print('edge intersection shadow safety: PASS')
