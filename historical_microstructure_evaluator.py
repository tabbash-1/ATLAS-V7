"""Evaluate the frozen historical microstructure replay under a preregistered protocol.

This module is intentionally strict:
- it NEVER recomputes historical features;
- it validates the immutable feature registry and preregistered protocol first;
- outcome_loader is not called unless both hashes/contracts pass;
- only the preregistered primary horizon is used for the edge decision;
- 24h remains descriptive only;
- retrospective evidence can never alter Production or live execution.
"""
from __future__ import annotations

import copy
import statistics

import historical_evaluation_protocol as protocol_mod
import historical_replay_registry as registry_mod

VERSION = 'ATLAS_HISTORICAL_MICROSTRUCTURE_EVALUATION_V1_PREREGISTERED_12H'


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _directional_return(raw_row, horizon_h, direction):
    raw = (raw_row or {}).get('forward_return_pct') or {}
    market_ret = _f(raw.get(str(int(horizon_h))))
    if market_ret is None:
        return None
    return market_ret if direction == 'LONG' else -market_ret if direction == 'SHORT' else None


def _metrics(vals):
    vals = [float(v) for v in vals if v is not None]
    if not vals:
        return {'n':0,'mean_pct':None,'median_pct':None,'positive_rate_pct':None}
    return {
        'n': len(vals),
        'mean_pct': round(sum(vals)/len(vals), 6),
        'median_pct': round(statistics.median(vals), 6),
        'positive_rate_pct': round(100.0*sum(v > 0 for v in vals)/len(vals), 4),
    }


def _fold_bounds(rows, folds):
    # Chronological fold assignment is made from FROZEN feature timestamps only.
    ordered = sorted(rows, key=lambda x:(int(x.get('forward_captured_at_ms') or 0), str(x.get('forward_id') or '')))
    n = len(ordered)
    out=[]
    for i in range(folds):
        a=(i*n)//folds
        b=((i+1)*n)//folds
        out.append(ordered[a:b])
    return out


def _authorized(registry_state, protocol_state):
    rman = (registry_state or {}).get('manifest')
    pman = (protocol_state or {}).get('manifest')
    if (registry_state or {}).get('status') != 'FROZEN_READY' or not (registry_state or {}).get('registration_locked'):
        return False, 'FEATURE_REGISTRY_NOT_FROZEN'
    if (protocol_state or {}).get('status') != 'PREREGISTERED' or not (protocol_state or {}).get('registration_locked'):
        return False, 'EVALUATION_PROTOCOL_NOT_PREREGISTERED'
    ok, err = registry_mod.validate_manifest(rman)
    if not ok:
        return False, f'FEATURE_REGISTRY_{err}'
    feature_hash = str((registry_state or {}).get('feature_dataset_sha256') or '')
    if not feature_hash or feature_hash != str((rman or {}).get('feature_dataset_sha256') or ''):
        return False, 'FEATURE_STATE_HASH_MISMATCH'
    ok, err = protocol_mod.validate_manifest(pman, feature_hash)
    if not ok:
        return False, f'PROTOCOL_{err}'
    if str((protocol_state or {}).get('protocol_hash') or '') != str((pman or {}).get('protocol_hash') or ''):
        return False, 'PROTOCOL_STATE_HASH_MISMATCH'
    return True, None


def evaluate(registry_state, protocol_state, outcome_loader):
    authorized, blocker = _authorized(registry_state, protocol_state)
    base = {
        'schema': VERSION,
        'research_only': True,
        'live_execution': False,
        'can_override_production': False,
        'retrospective_reconstruction': True,
        'forward_proof_equivalent': False,
        'outcome_loader_called': False,
        'primary_edge_claim': False,
        'status': 'BLOCKED' if not authorized else 'STARTING',
        'blockers': [blocker] if blocker else [],
    }
    if not authorized:
        return base

    rman = registry_state['manifest']
    pman = protocol_state['manifest']
    rules = copy.deepcopy(pman['rules'])
    frozen = copy.deepcopy(rman['rows'])
    primary_h = int(rules['primary_horizon_hours'])
    secondary_h = int(rules['secondary_descriptive_horizon_hours'])
    exposed_names = set(rules['primary_exposed_group'])
    control_names = set(rules['primary_control_group'])
    folds_n = int(rules['chronological_folds'])

    raw_rows = outcome_loader()
    base['outcome_loader_called'] = True
    by_id = {str(x.get('id')):x for x in raw_rows or [] if isinstance(x, dict) and x.get('id')}

    evaluated=[]
    missing_primary=0
    missing_secondary=0
    unclassified=0
    for feat in frozen:
        fid=str(feat.get('forward_id') or '')
        relation=str(feat.get('relation_to_signal') or '')
        if relation in exposed_names:
            group='EXPOSED_ALIGNED'
        elif relation in control_names:
            group='CONTROL_PREDECLARED'
        else:
            unclassified += 1
            continue
        raw=by_id.get(fid)
        p=_directional_return(raw, primary_h, feat.get('direction')) if raw else None
        s=_directional_return(raw, secondary_h, feat.get('direction')) if raw else None
        if p is None: missing_primary += 1
        if s is None: missing_secondary += 1
        evaluated.append({
            'forward_id':fid,
            'forward_captured_at_ms':int(feat.get('forward_captured_at_ms') or 0),
            'group':group,
            'relation_to_signal':relation,
            'primary_directional_return_pct':p,
            'secondary_directional_return_pct':s,
        })

    primary_matured=[x for x in evaluated if x['primary_directional_return_pct'] is not None]
    exposed=[x['primary_directional_return_pct'] for x in primary_matured if x['group']=='EXPOSED_ALIGNED']
    control=[x['primary_directional_return_pct'] for x in primary_matured if x['group']=='CONTROL_PREDECLARED']
    em=_metrics(exposed); cm=_metrics(control)

    delta_mean=(em['mean_pct']-cm['mean_pct']) if em['mean_pct'] is not None and cm['mean_pct'] is not None else None
    delta_pos=(em['positive_rate_pct']-cm['positive_rate_pct']) if em['positive_rate_pct'] is not None and cm['positive_rate_pct'] is not None else None

    fold_reports=[]
    positive_delta_folds=0
    for i, fold in enumerate(_fold_bounds(frozen, folds_n), start=1):
        ids={str(x.get('forward_id') or '') for x in fold}
        fx=[x for x in primary_matured if x['forward_id'] in ids]
        ev=[x['primary_directional_return_pct'] for x in fx if x['group']=='EXPOSED_ALIGNED']
        cv=[x['primary_directional_return_pct'] for x in fx if x['group']=='CONTROL_PREDECLARED']
        a=_metrics(ev); b=_metrics(cv)
        d=(a['mean_pct']-b['mean_pct']) if a['mean_pct'] is not None and b['mean_pct'] is not None else None
        if d is not None and d > 0: positive_delta_folds += 1
        fold_reports.append({'fold':i,'exposed':a,'control':b,'mean_delta_pct_points':round(d,6) if d is not None else None})

    secondary_exposed=[x['secondary_directional_return_pct'] for x in evaluated if x['group']=='EXPOSED_ALIGNED' and x['secondary_directional_return_pct'] is not None]
    secondary_control=[x['secondary_directional_return_pct'] for x in evaluated if x['group']=='CONTROL_PREDECLARED' and x['secondary_directional_return_pct'] is not None]

    thresholds=rules['edge_claim_thresholds']
    min_group=int(rules['minimum_matured_rows_per_primary_group'])
    blockers=[]
    if em['n'] < min_group: blockers.append('EXPOSED_GROUP_BELOW_PREREGISTERED_MINIMUM')
    if cm['n'] < min_group: blockers.append('CONTROL_GROUP_BELOW_PREREGISTERED_MINIMUM')
    sample_ok=not blockers
    edge = bool(
        sample_ok and
        delta_mean is not None and delta_mean >= float(thresholds['minimum_mean_return_delta_pct_points']) and
        delta_pos is not None and delta_pos >= float(thresholds['minimum_positive_rate_delta_percentage_points']) and
        positive_delta_folds >= int(thresholds['minimum_positive_mean_delta_folds'])
    )

    base.update({
        'status':'RETROSPECTIVE_EDGE_SUPPORTED' if edge else 'RETROSPECTIVE_EDGE_NOT_SUPPORTED' if sample_ok else 'INSUFFICIENT_PREDECLARED_GROUP_SAMPLE',
        'blockers':blockers,
        'feature_dataset_sha256':rman.get('feature_dataset_sha256'),
        'protocol_hash':pman.get('protocol_hash'),
        'primary_horizon_h':primary_h,
        'secondary_descriptive_horizon_h':secondary_h,
        'frozen_feature_rows':len(frozen),
        'joined_rows':len(evaluated),
        'primary_matured_rows':len(primary_matured),
        'missing_primary_rows':missing_primary,
        'missing_secondary_rows':missing_secondary,
        'unclassified_relation_rows':unclassified,
        'primary':{
            'exposed_aligned':em,
            'control_predeclared':cm,
            'mean_return_delta_pct_points':round(delta_mean,6) if delta_mean is not None else None,
            'positive_rate_delta_percentage_points':round(delta_pos,4) if delta_pos is not None else None,
            'positive_mean_delta_folds':positive_delta_folds,
            'chronological_folds':fold_reports,
            'thresholds':copy.deepcopy(thresholds),
        },
        'secondary_descriptive_only':{
            'exposed_aligned':_metrics(secondary_exposed),
            'control_predeclared':_metrics(secondary_control),
            'used_for_edge_claim':False,
        },
        'primary_edge_claim':edge,
        'interpretation':'RETROSPECTIVE_DISCOVERY_EVIDENCE_ONLY_NOT_FORWARD_PROOF_NOT_TP_SL_R',
    })
    return base
