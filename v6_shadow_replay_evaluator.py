#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

SRC=Path('status/v6-shadow-replay.json')
OUT=Path('status/v6-shadow-replay-evaluation.json')
CANDIDATES=['A_ATTRIBUTION_CLEANUP','B_VOLUME_QUALITY','C_VOLUME_PLUS_RS']
COVERAGES=['5','10','15','20','21']
HORIZONS=['12h','24h']

def delta(a,b):
    return None if a is None or b is None else round(a-b,4)

def main():
    p=json.loads(SRC.read_text())
    results={}
    for c in CANDIDATES:
        cells=[]
        for h in HORIZONS:
            eq=(p.get('comparisons',{}).get(h,{}).get('equal_coverage') or {})
            for k in COVERAGES:
                if k not in eq or 'BASELINE' not in eq[k] or c not in eq[k]:
                    continue
                bm=eq[k]['BASELINE']['metrics']; cm=eq[k][c]['metrics']
                cells.append({
                    'horizon':h,'coverage_n':int(k),
                    'win_rate_delta_pp':delta(cm.get('win_rate_pct'),bm.get('win_rate_pct')),
                    'mean_delta_pct':delta(cm.get('mean_pct'),bm.get('mean_pct')),
                    'median_delta_pct':delta(cm.get('median_pct'),bm.get('median_pct')),
                    'p10_delta_pct':delta(cm.get('p10_pct'),bm.get('p10_pct')),
                    'large_loss_delta_pp':delta(cm.get('loss_rate_le_minus_2pct'),bm.get('loss_rate_le_minus_2pct')),
                })
        n=len(cells)
        def pos(key): return sum(1 for x in cells if x.get(key) is not None and x[key] > 0)
        def nonworse_loss(): return sum(1 for x in cells if x.get('large_loss_delta_pp') is not None and x['large_loss_delta_pp'] <= 0)
        pass_rate=(pos('win_rate_delta_pp')+pos('mean_delta_pct')+pos('median_delta_pct')+pos('p10_delta_pct')+nonworse_loss())/(5*n) if n else 0
        results[c]={
            'cells_evaluated':n,
            'win_rate_improved_cells':pos('win_rate_delta_pp'),
            'mean_improved_cells':pos('mean_delta_pct'),
            'median_improved_cells':pos('median_delta_pct'),
            'p10_improved_cells':pos('p10_delta_pct'),
            'large_loss_nonworse_cells':nonworse_loss(),
            'robustness_score_pct':round(100*pass_rate,2),
            'cells':cells,
        }
    ranking=sorted(results, key=lambda c:results[c]['robustness_score_pct'], reverse=True)
    best=ranking[0] if ranking else None
    # Research gate is deliberately strict: broad improvement across horizons/coverage,
    # downside must be non-worse in >=70% of cells, and no auto-promotion.
    best_stats=results.get(best,{})
    n=best_stats.get('cells_evaluated',0)
    gate=bool(n and best_stats.get('robustness_score_pct',0)>=70 and best_stats.get('large_loss_nonworse_cells',0)/n>=0.70)
    out={
      'schema':'ATLAS_V6_SHADOW_REPLAY_EVALUATION_V1',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'ranking':ranking,
      'results':results,
      'best_candidate':best,
      'research_gate_pass':gate,
      'decision':'ADVANCE_TO_CHRONOLOGICAL_HOLDOUT' if gate else 'KEEP_RESEARCH_ONLY',
      'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_changed':False,'auto_promotion_enabled':False}
    }
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'best_candidate':best,'research_gate_pass':gate,'decision':out['decision']}))
if __name__=='__main__': main()
