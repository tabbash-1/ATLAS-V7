import winning_setup_fingerprint as m

def test_fingerprint_is_strict_and_frozen():
 good={"frozen_before_outcome":True,"htf_v2_eligible":True,"breakout_confirmed":True,"playbook":"BREAKOUT_CONFIRMED_LONG","htf_alignment_class":"CONDITIONAL_ALIGNED_12H_NEUTRAL","futures_alignment":"OPPOSED"}
 assert m.match(good) is True
 bad=dict(good,htf_v2_eligible=False);assert m.match(bad) is False
 bad=dict(good,htf_alignment_class="NO_ENTRY_CONFIRMATION_DIRECTION");assert m.match(bad) is False
 assert m.MIN_MATCHED==15 and m.MIN_CONTROL==15
