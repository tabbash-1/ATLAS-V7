#!/usr/bin/env python3
"""Research-only V6 candidate ranking analysis.

Uses the already-generated V6 attribution summary to propose a conservative
shadow ranking policy. It never changes Production scoring or thresholds.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

SRC=Path('status/v6-attribution-summary.json')
OUT=Path('status/v6-shadow-candidate-analysis.json')

def main():
    p=json.loads(SRC.read_text())
    out={
      'schema':'ATLAS_V6_SHADOW_CANDIDATE_ANALYSIS_V1',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'source_schema':p.get('schema'),
      'episodes':p.get('episodes'),
      'baseline':p.get('overall'),
      'diagnosis':{
        'trend_base':'ANTI_PREDICTIVE_IN_CURRENT_V6_SAMPLE',
        'direction_votes':'4_VOTES_DO_NOT_OUTPERFORM_3_VOTES',
        'relative_strength':'ALIGNED_STRONG_IS_POSITIVE_AT_24H',
        'volume':'RV_GTE_1_IS_STRONGLY_POSITIVE_AT_24H',
        'futures':'NO_STABLE_POSITIVE_MONOTONIC_SIGNAL',
        'structure':'CLOSE_PRIOR_STRUCTURE_IS_WEAK; VERY_CLOSE_IS_LESS_BAD_BUT_NOT_POSITIVE_OVERALL',
      },
      'candidate_policy':{
        'name':'V6_SHADOW_QUALITY_GATE_A',
        'mode':'RANKING_AND_FILTER_ONLY',
        'production_mutation':False,
        'rules':[
          {'rule':'relative_volume >= 1.0','reason':'V6 sample: 80% 24h wins, +2.2193% mean, n=5','priority':'HIGH'},
          {'rule':'relative_strength_reason == ALIGNED_STRONG','reason':'V6 sample: 60% 24h wins, +0.7214% mean, n=10','priority':'MEDIUM'},
          {'rule':'do not reward 4 votes over 3 votes','reason':'4 votes underperformed 3 votes at 12h and 24h','priority':'HIGH'},
          {'rule':'do not raise confidence solely from trend_base 68..72','reason':'higher trend_base underperformed 64..68','priority':'HIGH'},
          {'rule':'treat futures as secondary evidence until monotonicity improves','reason':'aligned/opposed buckets both negative at 24h','priority':'MEDIUM'},
        ],
        'shadow_quality_score_formula':'baseline_score + volume_quality_overlay + relative_strength_overlay; trend/vote/futures bonuses capped until revalidated',
      },
      'promotion_gate':{
        'status':'NOT_ELIGIBLE_FOR_PRODUCTION',
        'requirements':['evaluate candidate at record level against same independent V6 episodes','compare coverage, 12h/24h win rate, mean and median directional return','require no material degradation in downside tails','keep threshold unchanged during shadow test']
      },
      'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_changed':False,'auto_promotion_enabled':False}
    }
    OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'episodes':out['episodes'],'candidate':out['candidate_policy']['name'],'production_mutation':False}))
if __name__=='__main__': main()
