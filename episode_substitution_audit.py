#!/usr/bin/env python3
"""Audit counterfactual episode-substitution instability.

A dynamic counterfactual that removes rows before `independent()` can select
replacement episodes that were not in the baseline independent set. This audit
compares that dynamic replay with a fixed-anchor paired view so a filter is not
credited/blamed for unrelated replacement episodes.

Current case study: combined shadow baseline vs NEUTRAL-RS veto at 24h.
Research-only; Production is untouched.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import neutral_rs_veto_shadow as neutral

OUT = Path('status/episode-substitution-audit.json')
SCHEMA = 'ATLAS_EPISODE_SUBSTITUTION_AUDIT_V1'
H = 24


def eid(r):
    return f"{r['symbol']}|{r['direction']}|{r['captured_at'].isoformat()}"


def row_view(r):
    return {
        'episode_id': eid(r),
        'captured_at': r['captured_at'].isoformat(),
        'symbol': r['symbol'],
        'direction': r['direction'],
        'rs_reason': r.get('rs_reason'),
        'obstacle_reason': r.get('obstacle_reason'),
        'score': r.get('corrected_score'),
        'return_24h_pct': base.fnum(r.get('return_24h_pct')),
    }


def lane_rows(rows):
    return [r for r in rows if neutral.baseline_qualified(r)]


def independent24(rows):
    return base.independent(rows, H)


def split_hourly(hourly):
    return neutral.split(hourly)


def analyze_lane(rows):
    baseline_pool = lane_rows(rows)
    candidate_pool = [r for r in baseline_pool if not neutral.is_vetoed(r)]
    baseline_eps = independent24(baseline_pool)
    dynamic_candidate_eps = independent24(candidate_pool)

    baseline_ids = {eid(r): r for r in baseline_eps}
    candidate_ids = {eid(r): r for r in dynamic_candidate_eps}

    retained = [r for k,r in baseline_ids.items() if k in candidate_ids]
    removed = [r for k,r in baseline_ids.items() if k not in candidate_ids]
    replacements = [r for k,r in candidate_ids.items() if k not in baseline_ids]

    # Fixed-anchor candidate: do not allow later replacements. We keep baseline
    # episode anchors and simply reject anchors hit by the proposed veto.
    fixed_candidate = [r for r in baseline_eps if not neutral.is_vetoed(r)]
    fixed_removed = [r for r in baseline_eps if neutral.is_vetoed(r)]

    return {
        'pool_hours': {'baseline':len(baseline_pool),'candidate':len(candidate_pool)},
        'dynamic': {
            'baseline': base.stats(baseline_eps,H),
            'candidate': base.stats(dynamic_candidate_eps,H),
            'retained': base.stats(retained,H),
            'removed_from_baseline_set': base.stats(removed,H),
            'replacement_episodes': base.stats(replacements,H),
            'counts': {'baseline':len(baseline_eps),'candidate':len(dynamic_candidate_eps),'retained':len(retained),'removed':len(removed),'replacements':len(replacements)},
            'removed': [row_view(r) for r in removed],
            'replacements': [row_view(r) for r in replacements],
        },
        'fixed_anchor': {
            'baseline': base.stats(baseline_eps,H),
            'candidate': base.stats(fixed_candidate,H),
            'vetoed_baseline_anchors': base.stats(fixed_removed,H),
            'counts': {'baseline':len(baseline_eps),'candidate':len(fixed_candidate),'vetoed':len(fixed_removed)},
            'vetoed': [row_view(r) for r in fixed_removed],
        },
    }


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    train, holdout, cutoff = split_hourly(hourly)
    lanes = {
        'full': analyze_lane(hourly),
        'train': analyze_lane(train),
        'holdout': analyze_lane(holdout),
    }

    train_dyn = lanes['train']['dynamic']
    train_fix = lanes['train']['fixed_anchor']
    replacement_instability = bool(train_dyn['counts']['replacements'] > 0)
    fixed_supports_veto = bool(
        train_fix['vetoed_baseline_anchors']['n'] > 0
        and (train_fix['vetoed_baseline_anchors'].get('mean_pct') or 0) < 0
    )
    dynamic_conflicts = bool(
        train_dyn['baseline'].get('mean_pct') is not None
        and train_dyn['candidate'].get('mean_pct') is not None
        and train_dyn['candidate']['mean_pct'] < train_dyn['baseline']['mean_pct']
    )

    if replacement_instability and fixed_supports_veto and dynamic_conflicts:
        decision = 'COUNTERFACTUAL_CONTAMINATED_BY_EPISODE_SUBSTITUTION'
    elif not replacement_instability:
        decision = 'NO_EPISODE_SUBSTITUTION_DETECTED'
    else:
        decision = 'EPISODE_SUBSTITUTION_PRESENT_REVIEW_DETAILS'

    return {
        'schema':SCHEMA,
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'case':'COMBINED_SHADOW_PLUS_NEUTRAL_RS_VETO_24H',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'lanes':lanes,
        'diagnostic_decision':decision,
        'methodology_recommendation':'For filter counterfactuals, report both dynamic opportunity-sequence replay and fixed-baseline-anchor paired impact. Do not promote a filter when the two disagree; investigate replacement episodes first.',
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({
        'schema':r['schema'],'coverage':r['coverage'],'diagnostic_decision':r['diagnostic_decision'],
        'train_dynamic':r['lanes']['train']['dynamic'],
        'train_fixed_anchor':r['lanes']['train']['fixed_anchor'],
        'holdout_dynamic':r['lanes']['holdout']['dynamic'],
        'holdout_fixed_anchor':r['lanes']['holdout']['fixed_anchor'],
        'guardrails':r['guardrails'],
    },sort_keys=True,default=str))

if __name__=='__main__':
    main()
