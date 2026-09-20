"""Cost-aware comparison for Champion vs Reasoning Challenger."""
from __future__ import annotations
import execution_cost_model as costs

def net_directional_return(gross_return, decision, cost_bps):
 if str(decision).upper()=="WAIT": return float(gross_return),0.0
 if cost_bps is None:return None,None
 c=float(cost_bps)/10000.0
 return float(gross_return)-c,c

def compare(outcome, champion_decision, challenger_decision, cost_bps):
 cg=float(outcome["champion_directional_return"]); rg=float(outcome["challenger_directional_return"])
 cn,cc=net_directional_return(cg,champion_decision,cost_bps)
 rn,rc=net_directional_return(rg,challenger_decision,cost_bps)
 return {"champion_gross_return":cg,"challenger_gross_return":rg,
  "champion_net_return":round(cn,8) if cn is not None else None,
  "challenger_net_return":round(rn,8) if rn is not None else None,
  "champion_cost_return":round(cc,8) if cc is not None else None,
  "challenger_cost_return":round(rc,8) if rc is not None else None,
  "cost_bps_roundtrip":cost_bps,"cost_validated":cost_bps is not None}
