#!/usr/bin/env python3
"""Predeclared falsification test for RS_ALIGNED_STRONG as a 12h risk veto.

The nominee came from Candidate C failure diagnosis, so this is NOT pure OOS.
We keep coverage exactly equal by replacing vetoed top-V6 records with the next
highest baseline records. The rule is frozen: veto iff relative_strength_reason
== ALIGNED_STRONG. No thresholds or score weights are tuned here.
"""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from v6_shadow_replay import independent, ret, baseline, rs_reason

SRC = Path('status/wait-outcomes.json')
OUT = Path('status/v6-rs-aligned-veto-stability.json')
H = '12h'
FLAG = 'ALIGNED_STRONG'


def metrics(rows):
    vals=[ret(r,H) for r in rows if ret(r,H) is not None]
    if not vals: return {'n':0}
    vals=sorted(vals); n=len(vals)
    median=vals[n//2] if n%2 else (vals[n//2-1]+vals[n//2])/2
    p10=vals[max(0, int((n-1)*0.10))]
    return {
      'n':n,
      'mean_pct':round(sum(vals)/n,4),
      'median_pct':round(median,4),
      'win_rate_pct':round(100*sum(v>0 for v in vals)/n,2),
      'p10_pct':round(p10,4),
      'large_loss_rate_pct':round(100*sum(v<=-2 for v in vals)/n,2),
    }


def select_baseline(rows,k):
    eligible=[r for r in rows if ret(r,H) is not None]
    return sorted(eligible,key=baseline,reverse=True)[:k]


def select_veto_equal_coverage(rows,k):
    eligible=[r for r in rows if ret(r,H) is not None]
    ranked=sorted(eligible,key=baseline,reverse=True)
    clean=[r for r in ranked if rs_reason(r) != FLAG]
    flagged=[r for r in ranked if rs_reason(r) == FLAG]
    # Equal coverage. Use clean first; only fall back to flagged if there are not
    # enough clean observations to preserve k exactly.
    return (clean + flagged)[:k]


def compare(rows,k):
    b=select_baseline(rows,k); v=select_veto_equal_coverage(rows,k)
    bm,vm=metrics(b),metrics(v)
    delta={
      'win_rate_delta_pp':round(vm.get('win_rate_pct',0)-bm.get('win_rate_pct',0),2),
      'mean_delta_pct':round(vm.get('mean_pct',0)-bm.get('mean_pct',0),4),
      'median_delta_pct':round(vm.get('median_pct',0)-bm.get('median_pct',0),4),
      'p10_delta_pct':round(vm.get('p10_pct',0)-bm.get('p10_pct',0),4),
      'large_loss_delta_pp':round(vm.get('large_loss_rate_pct',0)-bm.get('large_loss_rate_pct',0),2),
    }
    return {
      'baseline':bm,'veto_equal_coverage':vm,'delta':delta,
      'quality_nonworse': delta['mean_delta_pct']>=0 and delta['median_delta_pct']>=0 and delta['win_rate_delta_pp']>=0,
      'downside_nonworse': delta['large_loss_delta_pp']<=0 and delta['p10_delta_pct']>=0,
      'baseline_flagged_count':sum(rs_reason(r)==FLAG for r in b),
      'veto_selected_flagged_count':sum(rs_reason(r)==FLAG for r in v),
      'veto_symbols':dict(sorted(Counter(str(r.get('symbol') or '').upper() for r in v).items())),
    }


def segment_eval(rows):
    n=sum(ret(r,H) is not None for r in rows)
    ks=sorted(set(k for k in (3,5,8,max(1,n//2)) if k<=n))
    cells={str(k):compare(rows,k) for k in ks}
    q=sum(int(c['quality_nonworse']) for c in cells.values())
    d=sum(int(c['downside_nonworse']) for c in cells.values())
    total=len(cells)
    return {
      'eligible_n':n,'cells':cells,
      'quality_nonworse_pct':round(100*q/total,2) if total else 0,
      'downside_nonworse_pct':round(100*d/total,2) if total else 0,
    }


def main():
    raw=json.loads(SRC.read_text()).get('records') or []
    eps=sorted(independent(raw),key=lambda r:r.get('_episode_time') or '')
    cut=max(1,int(len(eps)*0.70))
    prior=eps[:cut]; later=eps[cut:]
    prior_eval=segment_eval(prior); later_eval=segment_eval(later)

    # Leave-one-symbol-out on the later segment. This is a falsification check,
    # not an independent validation set because the nominee was discovered there.
    symbols=sorted({str(r.get('symbol') or '').upper() for r in later if ret(r,H) is not None and r.get('symbol')})
    jack={}; jq=jd=jt=0
    for sym in symbols:
        rows=[r for r in later if str(r.get('symbol') or '').upper()!=sym]
        n=sum(ret(r,H) is not None for r in rows)
        if n<5: continue
        k=min(5,n)
        c=compare(rows,k)
        jack[sym]={'eligible_n':n,'k':k,**c}
        jt+=1; jq+=int(c['quality_nonworse']); jd+=int(c['downside_nonworse'])

    prior_ok=prior_eval['quality_nonworse_pct']>=60 and prior_eval['downside_nonworse_pct']>=60
    later_ok=later_eval['quality_nonworse_pct']>=60 and later_eval['downside_nonworse_pct']>=60
    jack_q=(100*jq/jt) if jt else 0; jack_d=(100*jd/jt) if jt else 0
    jack_ok=jt>=4 and jack_q>=60 and jack_d>=60

    # A prospective shadow is allowed only when the exact veto is directionally
    # stable in both temporal segments and not dependent on one symbol.
    passed=bool(prior_ok and later_ok and jack_ok)
    report={
      'schema':'ATLAS_V6_RS_ALIGNED_VETO_STABILITY_V1',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'predeclared_rule':'VETO_12H_IF_RELATIVE_STRENGTH_REASON_EQUALS_ALIGNED_STRONG',
      'horizon':'12h',
      'selection_bias_note':'Nominee was discovered from the later segment; this is a falsification/stability test, not pure OOS.',
      'split':{'independent_episodes':len(eps),'prior_n':len(prior),'later_n':len(later),'fraction':0.70},
      'prior_segment':prior_eval,
      'later_segment':later_eval,
      'later_leave_one_symbol_out':jack,
      'summary':{
        'prior_stable':prior_ok,
        'later_stable':later_ok,
        'jackknife_cells':jt,
        'jackknife_quality_nonworse_pct':round(jack_q,2),
        'jackknife_downside_nonworse_pct':round(jack_d,2),
        'jackknife_stable':jack_ok,
      },
      'decision':'ALLOW_PROSPECTIVE_SHADOW_ONLY' if passed else 'REJECT_RS_ALIGNED_VETO',
      'guardrails':{
        'research_only':True,'production_threshold_changed':False,
        'production_score_changed':False,'auto_promotion_enabled':False,
        'production_veto_enabled':False,
      },
    }
    OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'decision':report['decision'],'summary':report['summary']}))

if __name__=='__main__': main()
