import profitability_prediction_side_specialist as s
def test_rule_frozen():
 assert s.actionable({"prediction":"UP","confidence":.45,"features":{"trend4":1,"trend12":1}})
 assert not s.actionable({"prediction":"DOWN","confidence":.59,"features":{"trend4":-1,"trend12":-1}})
 assert not s.actionable({"prediction":"DOWN","confidence":.8,"features":{"trend4":1,"trend12":-1}})
 assert s.safety()["threshold"]==68 and s.safety()["production_impact"]=="NONE"
