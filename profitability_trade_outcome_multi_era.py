"""Frozen multi-era exam for direct trade-outcome EV challenger.

Each era trains only on the 180 days ending before that era, then evaluates the
next 14 days. No cross-era reuse, no future features, EV rule remains > 0.
"""
import json,statistics
import profitability_trade_outcome_eval as oe
import profitability_trade_outcome_walk_forward as ow
DAY=86400000
# Ends are deliberately spaced so exam windows do not overlap.
ERA_TRAIN_ENDS=[1782709200000,1785301200000,1787893200000,1790485200000]
def combine(metrics):
 n=sum(x["n"] for x in metrics);net=sum(x["net_r"] for x in metrics)
 return {"n":n,"net_r":round(net,4),"weighted_avg_r":round(net/n,4) if n else None,
 "profitable_eras":sum(1 for x in metrics if x["net_r"]>0),"eras":len(metrics)}
def run():
 eras=[]
 for end in ERA_TRAIN_ENDS:
  r=ow.run(end,end+14*DAY,7)
  eras.append({"train_end_ms":end,"exam_end_ms":end+14*DAY,"baseline":r["aggregate"]["baseline"],
   "positive_ev":r["aggregate"]["positive_ev"],"by_side":r["by_side"],"by_symbol":r["by_symbol"],"training_rows":r["training_rows"]})
 return {"schema":"ATLAS_OUTCOME_MULTI_ERA_V1","era_days":14,"eras":eras,
  "aggregate":{"baseline":combine([x["baseline"] for x in eras]),"positive_ev":combine([x["positive_ev"] for x in eras])},
  "rule":"expected_r>0","safety":{"research_only":True,"production_impact":"NONE","threshold":68,
  "future_features":False,"rule_frozen_across_eras":True,"non_overlapping_exam_eras":True}}
if __name__=="__main__":print("ATLAS_OUTCOME_MULTI_ERA="+json.dumps(run(),sort_keys=True))
