from pathlib import Path
import profitability_entry_audit as m

def test_profitability_entry_audit_is_cost_adjusted_and_safe():
    x=m.build(Path(__file__).resolve().parents[1])
    m.validate(x)
    assert x["metric"]=="COST_ADJUSTED_NET_R"
    assert x["safety"]["uses_only_frozen_entry_features"] is True
    assert x["safety"]["can_override_production"] is False
    assert x["safety"]["can_create_trade"] is False
    assert x["safety"]["can_veto_trade"] is False
    names={c["name"] for c in x["cohorts"]}
    assert "LONG_HTF_V2_ELIGIBLE" in names
    assert "LONG_HTF_V2_INELIGIBLE" in names
