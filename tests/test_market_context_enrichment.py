from market_context_enrichment import enrich
from market_context_reasoning import build

def test_validated_derivatives_and_whales_can_veto_shadow_long():
 c=enrich({"trend_direction":"LONG","htf_alignment":"ALIGNED"},futures={"futures_evidence_validated":True,"orderbook_imbalance":-.3,"taker_ratio":.7,"funding_rate":.001},whale={"status":"READY_RESEARCH_ONLY","validated_entities":10,"consensus":"DISTRIBUTION"})
 x=build(c);assert x["decision"]=="WAIT" and x["reason"]=="CONTEXT_OPPOSES_TREND"
 assert x["can_override_canonical_decision"] is False

def test_unvalidated_inputs_remain_unknown_and_do_not_invent_veto():
 c=enrich({"trend_direction":"LONG","htf_alignment":"ALIGNED"},futures={"orderbook_imbalance":-.9},whale={"consensus":"DISTRIBUTION"},event={"impact_score":99,"direction":"NEGATIVE"})
 assert c["liquidity_bias"]=="UNKNOWN" and c["whale10_consensus"]=="UNKNOWN" and c["event_risk"]=="UNKNOWN"
 assert build(c)["decision"]=="LONG"

def test_confirmed_tier1_high_impact_event_blocks_shadow_trade():
 c=enrich({"trend_direction":"LONG","htf_alignment":"ALIGNED"},event={"source_quality":"TIER1","confirmed":True,"impact_score":90,"direction":"NEGATIVE"})
 x=build(c);assert x["decision"]=="WAIT" and x["reason"]=="EVENT_RISK"
