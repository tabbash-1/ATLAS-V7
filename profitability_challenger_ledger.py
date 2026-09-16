#!/usr/bin/env python3
"""Durable prospective challenger ledger; research/paper only."""
from __future__ import annotations
import json, math, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parent
RESEARCH=ROOT/'status/profitability-research-latest.json'; ATTR=ROOT/'status/analyst-forward-attribution-latest.json'
FORWARD=ROOT/'status/paper-portfolio-10k-analyst-latest.json'; REGISTRY=ROOT/'status/profitability-challenger-registry.json'; OUT=ROOT/'status/profitability-prospective-shadow-latest.json'
MIN_N=10; EXECUTION_COST_BPS=10.0; MAX_DD_R=3.0

def num(v):
 try:
  x=float(v); return x if math.isfinite(x) else None
 except Exception:return None
def tags(e):
 c=e.get('context') or {}; d={'symbol':e.get('symbol'),'direction':e.get('direction'),'playbook':c.get('playbook'),'regime':c.get('regime'),'score_bucket':c.get('score_bucket'),'breakout_confirmed':c.get('breakout_confirmed'),'futures_reason':c.get('futures_reason'),'relative_strength_reason':c.get('relative_strength_reason'),'extension_guard_reason':c.get('extension_guard_reason'),'structural_geometry_source':c.get('structural_geometry_source')}; return {k:str(v) for k,v in d.items() if v is not None}
def matches(e,f):
 t=tags(e); return all(t.get(k)==str(v) for k,v in f.items())
def metrics(vals):
 xs=[x for x in (num(v) for v in vals) if x is not None]; wins=[x for x in xs if x>0]; losses=[x for x in xs if x<0]; eq=peak=dd=0.0
 for x in xs: eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
 gp=sum(wins); gl=abs(sum(losses)); return {'n':len(xs),'avg_r':round(sum(xs)/len(xs),4) if xs else None,'net_r':round(sum(xs),4) if xs else None,'positive_pct':round(100*len(wins)/len(xs),2) if xs else None,'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else None),'max_drawdown_r':round(dd,4) if xs else None}
def load_or_freeze():
 if REGISTRY.exists(): return json.loads(REGISTRY.read_text())
 r=json.loads(RESEARCH.read_text()); now=datetime.now(timezone.utc).isoformat(); reg={'schema':'ATLAS_PROFITABILITY_CHALLENGER_REGISTRY_V1','frozen_at':now,'source_schema':r.get('schema'),'challengers':[{'challenger_id':x['challenger_id'],'frozen_filter':x['frozen_filter']} for x in r.get('challenger_registry') or []],'immutable_policy':'Never rewrite filters automatically; observations must be captured strictly after frozen_at.','production_effect':'NONE'}; REGISTRY.parent.mkdir(parents=True,exist_ok=True); REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)); return reg
def cost_adjust(e,r,trade):
 notional=num(trade.get('paper_notional_usd')); risk=num(trade.get('risk_usd')); source=str((e.get('settlement') or {}).get('market_source') or '')
 if notional is None or risk is None or risk<=0:return None,'MISSING_NOTIONAL_OR_RISK'
 execution_r=(EXECUTION_COST_BPS/10000.0)*notional/risk
 # Spot has no funding. Non-spot requires observed funding before promotion; never assume zero.
 funding_complete='SPOT' in source.upper()
 return round(r-execution_r,6), ('COMPLETE_SPOT_NO_FUNDING' if funding_complete else 'EXECUTION_ONLY_FUNDING_REQUIRED')
def build():
 reg=load_or_freeze(); attr=json.loads(ATTR.read_text()); freeze=reg['frozen_at']; forward=json.loads(FORWARD.read_text()) if FORWARD.exists() else {'trades':[]}; by_id={x.get('id'):x for x in forward.get('trades') or []}; rows=[]
 for e in attr.get('entries') or []:
  s=e.get('settlement') or {}; r=num(s.get('r_multiple')); ts=e.get('captured_at') or ''
  if ts>freeze and s.get('terminal') and r is not None:
   net,status=cost_adjust(e,r,by_id.get(e.get('id')) or {}); rows.append((e,r,net,status))
 challengers=[]
 for c in reg.get('challengers') or []:
  selected=[x for x in rows if matches(x[0],c['frozen_filter'])]; gross=metrics([x[1] for x in selected]); cost_vals=[x[2] for x in selected if x[2] is not None]; costm=metrics(cost_vals); funding_complete=bool(selected) and all(x[3]=='COMPLETE_SPOT_NO_FUNDING' for x in selected); cost_ready=bool(selected) and len(cost_vals)==len(selected) and funding_complete
  checks={'min_new_prospective_n':gross['n']>=MIN_N,'cost_adjusted_avg_r_positive':cost_ready and costm['avg_r'] is not None and costm['avg_r']>0,'cost_adjusted_profit_factor_gt_1':cost_ready and (costm['profit_factor']=='INF' or (isinstance(costm['profit_factor'],(int,float)) and costm['profit_factor']>1)),'cost_adjusted_max_drawdown_r_lte':cost_ready and costm['max_drawdown_r'] is not None and costm['max_drawdown_r']<=MAX_DD_R,'cost_and_funding_complete':cost_ready}
  challengers.append({**c,'prospective_gross':gross,'execution_cost_bps_roundtrip':EXECUTION_COST_BPS,'cost_adjusted':costm if cost_vals else None,'cost_coverage_n':len(cost_vals),'funding_statuses':sorted(set(x[3] for x in selected)),'checks':checks,'promotion_ready':all(checks.values()),'production_effect':'NONE'})
 return {'schema':'ATLAS_PROFITABILITY_PROSPECTIVE_SHADOW_V2_COST_AWARE','frozen_at':freeze,'new_terminal_market_observations':len(rows),'challengers':challengers,'promotion_policy':{'min_n':MIN_N,'execution_cost_bps_roundtrip':EXECUTION_COST_BPS,'max_drawdown_r':MAX_DD_R,'requires_cost_adjusted_positive_expectancy':True,'requires_funding_when_nonspot':True,'automatic_promotion':False},'cost_method':'execution_cost_R = roundtrip_bps/10000 * paper_notional_usd/risk_usd; spot funding=0; non-spot funding must be observed, never assumed.','stage':'PROSPECTIVE_SHADOW','production_mutation_authorized':False,'research_only':True}
def main():
 x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
