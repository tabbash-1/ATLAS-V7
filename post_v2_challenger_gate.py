#!/usr/bin/env python3
"""ATLAS post-V2 Challenger Gate.

Research/paper-only promotion readiness. It deliberately refuses to promote a
strategy while post-V2 prospective evidence is immature or adverse.
"""
from __future__ import annotations
import json, pathlib

ROOT=pathlib.Path(__file__).resolve().parent
WAIT=ROOT/'status/wait-missed-opportunity-latest.json'
LEARN=ROOT/'status/learning-engine-latest.json'
OUT=ROOT/'status/post-v2-challenger-gate-latest.json'
MIN_POST_V2_MATURED=100
MAX_MISSED_RATE_PCT=30.0
MIN_TRADE_N=30
MIN_TRADE_AVG_R=0.0


def build():
    wait=json.loads(WAIT.read_text())
    learn=json.loads(LEARN.read_text())
    post=((wait.get('cohorts') or {}).get('post_v2_forward') or {})
    trade=(((learn.get('evidence') or {}).get('trade_by_horizon') or {}).get('12h') or {})
    matured=int(post.get('matured_classified') or 0)
    missed=post.get('missed_rate_pct')
    trade_n=int(trade.get('n') or 0)
    avg_r=trade.get('avg_r')
    checks={
      'post_v2_matured_sample': matured >= MIN_POST_V2_MATURED,
      'post_v2_wait_missed_rate': missed is not None and float(missed) <= MAX_MISSED_RATE_PCT,
      'trade_sample': trade_n >= MIN_TRADE_N,
      'trade_expectancy': avg_r is not None and float(avg_r) > MIN_TRADE_AVG_R,
      'edge_proven_by_learning_engine': bool((learn.get('proof_status') or {}).get('edge_proven')),
    }
    ready=all(checks.values())
    return {
      'schema':'ATLAS_POST_V2_CHALLENGER_GATE_V1',
      'product_horizon':'4-12H',
      'epoch':wait.get('performance_epoch'),
      'observed':{'post_v2_matured':matured,'post_v2_wait_missed_rate_pct':missed,'trade_n_12h':trade_n,'trade_avg_r_12h':avg_r},
      'requirements':{'min_post_v2_matured':MIN_POST_V2_MATURED,'max_wait_missed_rate_pct':MAX_MISSED_RATE_PCT,'min_trade_n':MIN_TRADE_N,'min_trade_avg_r_exclusive':MIN_TRADE_AVG_R},
      'checks':checks,
      'promotion_ready':ready,
      'decision':'ELIGIBLE_FOR_MANUAL_PROMOTION_REVIEW' if ready else 'KEEP_BASELINE_AND_COLLECT_FORWARD_EVIDENCE',
      'production_mutation_authorized':False,
      'automatic_promotion':False,
      'live_execution':False,
      'research_only':True,
      'note':'Passing this gate is necessary, not sufficient. Candidate-specific frozen shadow/walk-forward/cost evidence remains required.'
    }


def main():
    out=build(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,indent=2,sort_keys=True)); print(json.dumps(out,indent=2,sort_keys=True))

if __name__=='__main__': main()
