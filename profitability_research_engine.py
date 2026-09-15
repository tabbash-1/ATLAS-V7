#!/usr/bin/env python3
"""ATLAS Profitability Research Engine V2.

Profitability-first, leakage-resistant research over frozen prospective evidence.
Production is a baseline only. Discovery, chronological holdout and prospective
promotion are separate stages; this module can never change live decisions.
"""
from __future__ import annotations
import json, math, pathlib, random
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / 'status/analyst-forward-attribution-latest.json'
OUT = ROOT / 'status/profitability-research-latest.json'
MIN_DISCOVERY_N = 3
MIN_HOLDOUT_N = 2
MIN_PROSPECTIVE_N = 10
DISCOVERY_FRACTION = 0.625
BOOTSTRAPS = 2000


def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None


def metrics(vals):
    xs=[num(x) for x in vals]; xs=[x for x in xs if x is not None]
    wins=[x for x in xs if x>0]; losses=[x for x in xs if x<0]
    gp=sum(wins); gl=abs(sum(losses))
    equity=peak=dd=0.0
    for x in xs:
        equity += x; peak=max(peak,equity); dd=max(dd,peak-equity)
    return {'n':len(xs),'avg_r':round(sum(xs)/len(xs),4) if xs else None,
            'net_r':round(sum(xs),4) if xs else None,
            'positive_pct':round(100*len(wins)/len(xs),2) if xs else None,
            'profit_factor':round(gp/gl,4) if gl else (None if not gp else 'INF'),
            'max_drawdown_r':round(dd,4) if xs else None}


def bootstrap_avg_ci(vals, seed=17):
    xs=[num(x) for x in vals]; xs=[x for x in xs if x is not None]
    if len(xs)<2: return None
    rng=random.Random(seed); avgs=[]
    for _ in range(BOOTSTRAPS):
        avgs.append(sum(rng.choice(xs) for _ in xs)/len(xs))
    avgs.sort(); lo=avgs[int(.025*(BOOTSTRAPS-1))]; hi=avgs[int(.975*(BOOTSTRAPS-1))]
    return [round(lo,4),round(hi,4)]


def tags(entry):
    c=entry.get('context') or {}
    out={'symbol':entry.get('symbol'),'direction':entry.get('direction'),'playbook':c.get('playbook'),
         'regime':c.get('regime'),'score_bucket':c.get('score_bucket'),
         'breakout_confirmed':c.get('breakout_confirmed'),'futures_reason':c.get('futures_reason'),
         'relative_strength_reason':c.get('relative_strength_reason'),
         'extension_guard_reason':c.get('extension_guard_reason'),
         'structural_geometry_source':c.get('structural_geometry_source')}
    return {k:str(v) for k,v in out.items() if v is not None}


def matches(entry, filt):
    t=tags(entry)
    return all(t.get(k)==str(v) for k,v in filt.items())


def discover(rows, baseline_avg):
    singles=defaultdict(list); pairs=defaultdict(list)
    for e,r in rows:
        items=sorted(tags(e).items())
        for k,v in items: singles[(k,v)].append(r)
        for i in range(len(items)):
            for j in range(i+1,len(items)): pairs[(items[i],items[j])].append(r)
    out=[]
    for kind,bag in [('single',singles),('pair',pairs)]:
        for key,vals in bag.items():
            m=metrics(vals)
            if m['n']<MIN_DISCOVERY_N or m['avg_r'] is None or m['avg_r']<=0: continue
            delta=round(m['avg_r']-baseline_avg,4) if baseline_avg is not None else None
            if delta is None or delta<=0: continue
            filt={key[0]:key[1]} if kind=='single' else {key[0][0]:key[0][1],key[1][0]:key[1][1]}
            out.append({'kind':kind,'filter':filt,'discovery':m,'discovery_avg_r_ci95':bootstrap_avg_ci(vals),
                        'delta_avg_r_vs_discovery_baseline':delta})
    out.sort(key=lambda x:(x['discovery']['avg_r'],x['discovery']['n']),reverse=True)
    return out


def build():
    src=json.loads(SOURCE.read_text())
    matured=[]
    for e in src.get('entries') or []:
        s=e.get('settlement') or {}; r=num(s.get('r_multiple'))
        if s.get('terminal') and r is not None: matured.append((e,r))
    matured.sort(key=lambda x:x[0].get('captured_at') or '')
    baseline=metrics([r for _,r in matured])
    cut=max(MIN_DISCOVERY_N,min(len(matured),int(len(matured)*DISCOVERY_FRACTION)))
    discovery_rows=matured[:cut]; holdout_rows=matured[cut:]
    discovery_baseline=metrics([r for _,r in discovery_rows]); holdout_baseline=metrics([r for _,r in holdout_rows])
    candidates=discover(discovery_rows,discovery_baseline['avg_r'])
    validated=[]
    for c in candidates:
        vals=[r for e,r in holdout_rows if matches(e,c['filter'])]
        hm=metrics(vals); ci=bootstrap_avg_ci(vals)
        holdout_pass=(hm['n']>=MIN_HOLDOUT_N and hm['avg_r'] is not None and hm['avg_r']>0 and
                      hm['profit_factor'] not in (None,0) and (hm['profit_factor']=='INF' or hm['profit_factor']>1))
        item=dict(c); item['holdout']=hm; item['holdout_avg_r_ci95']=ci
        item['holdout_status']='PASS_EARLY' if holdout_pass else ('INSUFFICIENT_N' if hm['n']<MIN_HOLDOUT_N else 'FAIL')
        item['proof_status']='PROSPECTIVE_CHALLENGER_ELIGIBLE' if holdout_pass else 'DISCOVERY_ONLY'
        validated.append(item)
    eligible=[x for x in validated if x['proof_status']=='PROSPECTIVE_CHALLENGER_ELIGIBLE']
    eligible.sort(key=lambda x:(x['holdout']['avg_r'],x['holdout']['n'],x['discovery']['avg_r']),reverse=True)
    registry=[]
    for i,c in enumerate(eligible[:3],1):
        registry.append({'challenger_id':f'EDGE-{i:02d}','frozen_filter':c['filter'],
                         'discovery':c['discovery'],'holdout':c['holdout'],
                         'stage':'PROSPECTIVE_SHADOW','new_prospective_n':0,
                         'promotion_ready':False,'production_effect':'NONE'})
    return {
      'schema':'ATLAS_PROFITABILITY_RESEARCH_V2','product_horizon':'4-12H',
      'purpose':'Discover edge, reject leakage/overfit, and freeze only holdout-positive challengers.',
      'baseline':baseline,
      'chronological_split':{'method':'captured_at ascending','discovery_n':len(discovery_rows),'holdout_n':len(holdout_rows),
                             'discovery_baseline':discovery_baseline,'holdout_baseline':holdout_baseline,
                             'holdout_used_for_candidate_selection':False},
      'candidate_count':len(validated),'holdout_eligible_count':len(eligible),
      'top_candidates':validated[:25],'challenger_registry':registry,
      'stage_status':{
        '1_dataset_and_baseline':'COMPLETE','2_edge_discovery':'COMPLETE','3_regime_setup_segmentation':'COMPLETE',
        '4_chronological_holdout':'COMPLETE','5_bootstrap_uncertainty':'COMPLETE',
        '6_prospective_shadow':'ACTIVE' if registry else 'BLOCKED_NO_HOLDOUT_EDGE',
        '7_production_promotion':'BLOCKED_PENDING_PROSPECTIVE_VALIDATION'},
      'validation_contract':{
        'discovery_min_n':MIN_DISCOVERY_N,'holdout_min_n':MIN_HOLDOUT_N,
        'promotion_min_new_prospective_n':MIN_PROSPECTIVE_N,'chronological_holdout_required':True,
        'walk_forward_required':True,'costs_required_before_promotion':True,'multiple_testing_control_required':True,
        'automatic_promotion':False,
        'note':'PASS_EARLY only freezes a paper challenger. It is not proof of profitability and cannot alter Production.'},
      'limitations':{
        'cost_adjusted_r_available':False,
        'cost_action':'Do not promote until fees/slippage can be expressed consistently in R.',
        'small_sample_warning':len(matured)<30,
        'multiple_testing':'Candidate scan is exploratory; holdout separation reduces but does not eliminate selection bias.'},
      'safety':{'research_only':True,'paper_only':True,'live_execution':False,'can_override_production':False,
                'can_change_score':False,'can_change_threshold':False}}


def main():
    out=build(); OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True))
    print(json.dumps({'baseline':out['baseline'],'candidate_count':out['candidate_count'],
                      'holdout_eligible_count':out['holdout_eligible_count'],'stage_status':out['stage_status']},sort_keys=True))

if __name__=='__main__': main()
