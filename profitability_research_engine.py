#!/usr/bin/env python3
"""ATLAS Profitability Research Engine V1.

Discovers *candidate* 4-12H edge pockets from frozen prospective analyst evidence.
Research only: never changes Production. Candidate discovery is deliberately
separated from proof; small cohorts cannot authorize promotion.
"""
from __future__ import annotations
import json, math, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / 'status/analyst-forward-attribution-latest.json'
OUT = ROOT / 'status/profitability-research-latest.json'

MIN_DISCOVERY_N = 3
MIN_VALIDATION_N = 10


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def metrics(vals):
    xs = [num(x) for x in vals]
    xs = [x for x in xs if x is not None]
    wins = [x for x in xs if x > 0]
    losses = [x for x in xs if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        'n': len(xs),
        'avg_r': round(sum(xs)/len(xs), 4) if xs else None,
        'net_r': round(sum(xs), 4) if xs else None,
        'positive_pct': round(100*len(wins)/len(xs), 2) if xs else None,
        'profit_factor': round(gross_profit/gross_loss, 4) if gross_loss else (None if not gross_profit else 'INF'),
    }


def tags(entry):
    c = entry.get('context') or {}
    out = {
        'symbol': entry.get('symbol'),
        'direction': entry.get('direction'),
        'playbook': c.get('playbook'),
        'regime': c.get('regime'),
        'score_bucket': c.get('score_bucket'),
        'breakout_confirmed': c.get('breakout_confirmed'),
        'futures_reason': c.get('futures_reason'),
        'relative_strength_reason': c.get('relative_strength_reason'),
        'extension_guard_reason': c.get('extension_guard_reason'),
        'structural_geometry_source': c.get('structural_geometry_source'),
    }
    return {k:str(v) for k,v in out.items() if v is not None}


def build():
    src = json.loads(SOURCE.read_text())
    matured = []
    for e in src.get('entries') or []:
        s = e.get('settlement') or {}
        r = num(s.get('r_multiple'))
        if s.get('terminal') and r is not None:
            matured.append((e, r))

    baseline = metrics([r for _,r in matured])
    singles = defaultdict(list)
    pairs = defaultdict(list)
    for e,r in matured:
        t = tags(e)
        items = sorted(t.items())
        for k,v in items:
            singles[(k,v)].append(r)
        for i in range(len(items)):
            for j in range(i+1,len(items)):
                pairs[(items[i],items[j])].append(r)

    candidates = []
    for kind, bag in [('single', singles), ('pair', pairs)]:
        for key, vals in bag.items():
            m = metrics(vals)
            if m['n'] < MIN_DISCOVERY_N:
                continue
            delta = None if baseline['avg_r'] is None or m['avg_r'] is None else round(m['avg_r']-baseline['avg_r'],4)
            if m['avg_r'] is not None and m['avg_r'] > 0 and delta is not None and delta > 0:
                filt = {key[0]:key[1]} if kind == 'single' else {key[0][0]:key[0][1], key[1][0]:key[1][1]}
                candidates.append({'kind':kind,'filter':filt,'metrics':m,'delta_avg_r_vs_baseline':delta,'proof_status':'DISCOVERY_ONLY'})
    candidates.sort(key=lambda x:(x['metrics']['avg_r'],x['metrics']['n']), reverse=True)

    return {
        'schema':'ATLAS_PROFITABILITY_RESEARCH_V1',
        'product_horizon':'4-12H',
        'purpose':'Find candidate positive-expectancy pockets before any Production change.',
        'baseline':baseline,
        'candidate_count':len(candidates),
        'top_candidates':candidates[:25],
        'validation_contract':{
            'discovery_min_n':MIN_DISCOVERY_N,
            'promotion_min_new_prospective_n':MIN_VALIDATION_N,
            'chronological_holdout_required':True,
            'walk_forward_required':True,
            'costs_required_before_promotion':True,
            'automatic_promotion':False,
            'note':'Discovery performance is not proof. Candidate rules must be frozen before new prospective observations.'
        },
        'safety':{
            'research_only':True,'paper_only':True,'live_execution':False,
            'can_override_production':False,'can_change_score':False,'can_change_threshold':False
        }
    }


def main():
    out = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps({'baseline':out['baseline'],'candidate_count':out['candidate_count']}, sort_keys=True))

if __name__ == '__main__':
    main()
