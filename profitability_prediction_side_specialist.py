"""Pre-registered side-specialist challenger for ATLAS Prediction Engine.

Rule frozen before the new temporal exam:
- UP: actionable at P>=0.45.
- DOWN: actionable only at P>=0.60 and both 4H/12H trend are non-positive.
This is a research challenger only; it cannot alter Production.
"""
VERSION="ATLAS_PREDICTION_SIDE_SPECIALIST_V1"
UP_MIN_P=.45
DOWN_MIN_P=.60

def actionable(prediction):
    side=prediction["prediction"]; p=prediction["confidence"]; x=prediction["features"]
    if side=="UP": return p>=UP_MIN_P
    if side=="DOWN": return p>=DOWN_MIN_P and x["trend4"]<=0 and x["trend12"]<=0
    return False

def safety():
    return {"research_only":True,"production_impact":"NONE","threshold":68,
      "rule_pre_registered":True,"up_min_p":UP_MIN_P,"down_min_p":DOWN_MIN_P,
      "down_requires_4h_12h_nonpositive":True}
