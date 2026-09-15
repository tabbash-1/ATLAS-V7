#!/usr/bin/env python3
import post_v2_challenger_gate as g
out=g.build()
assert out['schema']=='ATLAS_POST_V2_CHALLENGER_GATE_V1'
assert out['product_horizon']=='4-12H'
assert out['automatic_promotion'] is False
assert out['production_mutation_authorized'] is False
assert out['live_execution'] is False
assert out['research_only'] is True
assert out['requirements']['min_post_v2_matured'] >= 100
assert out['requirements']['min_trade_n'] >= 30
if not all(out['checks'].values()):
    assert out['promotion_ready'] is False
    assert out['decision']=='KEEP_BASELINE_AND_COLLECT_FORWARD_EVIDENCE'
print('post-v2 challenger gate safety: PASS')
