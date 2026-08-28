#!/usr/bin/env python3
"""Chronological stress test for the frozen V6 shadow candidate C.

Candidate C is already frozen by the prior replay. This script evaluates only the
latest 30% of independent V6 episodes versus the baseline ranking at equal
coverage. Because candidate selection used the earlier full replay, this is
explicitly labeled post-selection chronological holdout, not a pristine OOS test.
No Production state is changed.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from v6_shadow_replay import independent, ret, metrics, baseline, score_C

SRC=Path('status/wait-outcomes.json')
OUT=Path('status/v6-chronological-holdout.json')


def ranked_metrics(rows,h,fn,k):
    eligible=[r for r in rows if ret(r,h) is not None]
    selected=sorted(eligible,key=lambda r:(fn(r),baseline(r)),reverse=True)[:k]
    return metrics(selected,h)


def main():
    raw=json.loads(SRC.read_text()).get('records') or []
    eps=sorted(independent(raw), key=lambda r:r.get('_episode_time') or '')
    cut=max(1,int(len(eps)*0.70))
    train,test=eps[:cut],eps[cut:]
    report={
      'schema':'ATLAS_V6_POST_SELECTION_CHRONOLOGICAL_HOLDOUT_V1',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'candidate':'C_VOLUME_PLUS_RS',
      'split':{'train_fraction':0.70,'test_fraction':0.30,'train_n':len(train),'test_n':len(test),'cut_episode_time':test[0].get('_episode_time') if test else None},
      'limitation':'Candidate C was chosen using the prior full-sample replay. This is a temporal generalization stress test, not a pristine untouched out-of-sample selection test.',
      'horizons':{},
      'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_changed':False,'auto_promotion_enabled':False}
    }
    horizon_passes=[]
    for h in ('12h','24h'):
        eligible=sum(ret(r,h) is not None for r in test)
        ks=sorted(set(k for k in (3,5,8,max(1,eligible//2)) if k<=eligible))
        cells={}
        wins=0; safe=0; evaluated=0
        for k in ks:
            b=ranked_metrics(test,h,baseline,k); c=ranked_metrics(test,h,score_C,k)
            if not b.get('n') or not c.get('n'): continue
            evaluated+=1
            delta={
              'win_rate_delta_pp':round((c['win_rate_pct'] or 0)-(b['win_rate_pct'] or 0),2),
              'mean_delta_pct':round((c['mean_pct'] or 0)-(b['mean_pct'] or 0),4),
              'median_delta_pct':round((c['median_pct'] or 0)-(b['median_pct'] or 0),4),
              'p10_delta_pct':round((c['p10_pct'] or 0)-(b['p10_pct'] or 0),4),
              'large_loss_delta_pp':round((c['loss_rate_le_minus_2pct'] or 0)-(b['loss_rate_le_minus_2pct'] or 0),2),
            }
            if delta['win_rate_delta_pp']>=0 and delta['mean_delta_pct']>=0 and delta['median_delta_pct']>=0: wins+=1
            if delta['large_loss_delta_pp']<=0: safe+=1
            cells[str(k)]={'baseline':b,'candidate':c,'delta':delta}
        pass_h=bool(evaluated and wins/evaluated>=0.60 and safe/evaluated>=0.60)
        horizon_passes.append(pass_h)
        report['horizons'][h]={'eligible_test_n':eligible,'cells':cells,'cells_evaluated':evaluated,'quality_nonworse_or_better_cells':wins,'downside_nonworse_cells':safe,'pass':pass_h}
    report['decision']='PASS_TEMPORAL_STRESS_TEST' if all(horizon_passes) else 'FAIL_OR_INCONCLUSIVE_TEMPORAL_STRESS_TEST'
    report['next_step']='PROSPECTIVE_SHADOW_ONLY' if all(horizon_passes) else 'REVISE_OR_REJECT_CANDIDATE'
    OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'episodes':len(eps),'test_n':len(test),'decision':report['decision'],'next_step':report['next_step']}))

if __name__=='__main__': main()
