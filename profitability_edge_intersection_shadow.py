#!/usr/bin/env python3
"""Durable cost-aware prospective shadow for RS_SCORE_STRUCTURE_V1."""
from __future__ import annotations
import json, math, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parent
ATTR=ROOT/'status/analyst-forward-attribution-latest.json'
FORWARD=ROOT/'status/paper-portfolio-10k-analyst-latest.json'
REG=ROOT/'status/profitability-edge-intersection-registry.json'
OUT=ROOT/'status/profitability-edge-intersection-shadow-latest.json'
MIN_EARLY_N=10; MIN_PROMOTION_N=30; EXECUTION_COST_BPS=10.0; MAX_DD_R=3.0

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def ts(v):
    if not v:return None
    try:
        x=str(v).replace('Z','+00:00'); d=datetime.fromisoformat(x)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return None

def getv(e,key):
    c=e.get('context') or {}
    aliases={'score':['score'],'relative_strength_adjustment':['relative_strength_adjustment','rs_adjustment'],
             'obstacle_adjustment':['obstacle_adjustment','prior_structure_obstacle_adjustment']}
    for k in aliases[key]:
        for d in (c,e):
            if isinstance(d,dict):
                x=num(d.get(k))
                if x is not None:return x
    return None

def met(rs):
    if not rs:return {'n':0,'avg_r':None,'net_r':None,'positive_pct':None,'profit_factor':None,'max_drawdown_r':None}
    w=[x for x in rs if x>0]; l=[x for x in rs if x<0]; gp=sum(w); gl=abs(sum(l)); eq=peak=dd=0.0
    for x in rs: eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    return {'n':len(rs),'avg_r':round(sum(rs)/len(rs),4),'net_r':round(sum(rs),4),'positive_pct':round(100*len(w)/len(rs),2),
            'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else None),'max_drawdown_r':round(dd,4)}

def cost_adjust(e,r,tr):
    notional=num(tr.get('paper_notional_usd')); risk=num(tr.get('risk_usd')); source=str((e.get('settlement') or {}).get('market_source') or '')
    if notional is None or risk is None or risk<=0:return None,'MISSING_NOTIONAL_OR_RISK'
    net=r-(EXECUTION_COST_BPS/10000.0)*notional/risk
    if 'SPOT' in source.upper():return round(net,6),'COMPLETE_SPOT_NO_FUNDING'
    return round(net,6),'EXECUTION_ONLY_FUNDING_REQUIRED'

def build():
    reg=json.loads(REG.read_text()); attr=json.loads(ATTR.read_text()); forward=json.loads(FORWARD.read_text()) if FORWARD.exists() else {'trades':[]}
    freeze=ts(reg.get('frozen_at')); th=reg['frozen_thresholds']; by_id={x.get('id'):x for x in forward.get('trades') or []}
    if freeze is None:raise RuntimeError('invalid frozen_at')
    selected=[]; post_freeze_terminal=0
    for e in attr.get('entries') or []:
        s=e.get('settlement') or {}; r=num(s.get('r_multiple')); captured=ts(e.get('captured_at'))
        if not s.get('terminal') or r is None or captured is None or captured<=freeze:continue
        post_freeze_terminal+=1
        vals={k:getv(e,k) for k in th}; admit=all(vals[k] is not None and vals[k]>=num(th[k]) for k in th)
        if not admit:continue
        net,status=cost_adjust(e,r,by_id.get(e.get('id')) or {})
        selected.append({'id':e.get('id'),'captured_at':e.get('captured_at'),'symbol':e.get('symbol'),'direction':e.get('direction'),'gross_r':r,'net_r_after_execution_cost':net,'cost_status':status,'values':vals})
    gross=met([x['gross_r'] for x in selected]); nets=[x['net_r_after_execution_cost'] for x in selected if x['net_r_after_execution_cost'] is not None]; netm=met(nets)
    cost_complete=bool(selected) and len(nets)==len(selected) and all(x['cost_status']=='COMPLETE_SPOT_NO_FUNDING' for x in selected)
    pf=netm['profit_factor']; early=(gross['n']>=MIN_EARLY_N and cost_complete and netm['avg_r'] is not None and netm['avg_r']>0 and (pf=='INF' or isinstance(pf,(int,float)) and pf>1))
    promotion=(gross['n']>=MIN_PROMOTION_N and early and netm['max_drawdown_r'] is not None and netm['max_drawdown_r']<=MAX_DD_R)
    return {'schema':'ATLAS_EDGE_INTERSECTION_SHADOW_V2_DURABLE_COST_AWARE','hypothesis_id':reg['hypothesis_id'],'horizon':'4-12H','frozen_at':reg['frozen_at'],'frozen_thresholds':th,'rule':reg['rule'],
            'post_freeze_terminal_market_observations':post_freeze_terminal,'prospective_new_n':gross['n'],'prospective_observations':selected,'prospective_gross':gross,'prospective_cost_adjusted':netm if nets else None,
            'execution_cost_bps_roundtrip':EXECUTION_COST_BPS,'cost_and_funding_complete':cost_complete,'minimum_early_review_n':MIN_EARLY_N,'minimum_promotion_n':MIN_PROMOTION_N,'max_drawdown_r_for_promotion':MAX_DD_R,
            'early_review_ready':early,'promotion_ready':promotion,'automatic_promotion':False,'production_mutation_authorized':False,'decision':'COLLECT_PROSPECTIVE_EVIDENCE' if not promotion else 'ELIGIBLE_FOR_MANUAL_PROMOTION_REVIEW',
            'cost_method':'execution_cost_R = roundtrip_bps/10000 * paper_notional_usd/risk_usd; spot funding=0; non-spot funding must be observed.',
            'warnings':['Historical discovery/holdout never count toward prospective_new_n.','Promotion requires at least 30 new terminal observations and complete cost/funding evidence.','No automatic Production mutation.']}

def main():
    x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
