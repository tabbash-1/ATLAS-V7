"""Forward-only evaluator for the preregistered microstructure cohort V1."""
from __future__ import annotations

import copy
import statistics

import prospective_microstructure_cohort as cohort_mod

VERSION='ATLAS_PROSPECTIVE_MICROSTRUCTURE_EVALUATION_V1_12H'


def _f(v):
    try:return float(v)
    except Exception:return None


def _ret(row,h):
    market=_f(((row or {}).get('forward_return_pct') or {}).get(str(int(h))))
    if market is None:return None
    d=str((row or {}).get('direction') or '').upper()
    return market if d=='LONG' else -market if d=='SHORT' else None


def _metrics(vals):
    vals=[float(v) for v in vals if v is not None]
    if not vals:return {'n':0,'mean_pct':None,'median_pct':None,'positive_rate_pct':None}
    return {
        'n':len(vals),
        'mean_pct':round(sum(vals)/len(vals),6),
        'median_pct':round(statistics.median(vals),6),
        'positive_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),4),
    }


def _authorized(cohort_state):
    if (cohort_state or {}).get('status')!='PREREGISTERED' or not (cohort_state or {}).get('registration_locked'):
        return False,'COHORT_NOT_PREREGISTERED'
    man=(cohort_state or {}).get('manifest')
    ok,err=cohort_mod.validate_manifest(man)
    if not ok:return False,f'COHORT_{err}'
    if str((cohort_state or {}).get('cohort_hash') or '') != str((man or {}).get('cohort_hash') or ''):
        return False,'COHORT_STATE_HASH_MISMATCH'
    return True,None


def _folds(rows,n):
    rows=sorted(rows,key=lambda r:(int(r.get('captured_at_ms') or 0),str(r.get('id') or '')))
    return [rows[(i*len(rows))//n:((i+1)*len(rows))//n] for i in range(n)]


def evaluate(cohort_state,outcome_loader):
    ok,blocker=_authorized(cohort_state)
    base={
        'schema':VERSION,'research_only':True,'live_execution':False,'can_override_production':False,
        'forward_proof_cohort':True,'historical_rows_allowed':False,'outcome_loader_called':False,
        'primary_edge_claim':False,'status':'BLOCKED' if not ok else 'STARTING','blockers':[blocker] if blocker else [],
    }
    if not ok:return base
    man=cohort_state['manifest']; rules=man['rules']; start=int(man['cohort_start_ms'])
    freeze_schema=man['eligible_freeze_schema']; primary_h=int(rules['primary_horizon_hours']); secondary_h=int(rules['secondary_descriptive_horizon_hours'])
    exposed=set(rules['exposed_group']); control=set(rules['control_group'])

    raw=outcome_loader(); base['outcome_loader_called']=True
    eligible=[]; rejected_old=0; rejected_schema=0; rejected_relation=0
    for r in raw or []:
        if not isinstance(r,dict):continue
        if int(r.get('captured_at_ms') or 0) < start:
            rejected_old+=1; continue
        if r.get('microstructure_freeze_schema') != freeze_schema:
            rejected_schema+=1; continue
        relation=str(r.get('microstructure_relation_at_entry') or '')
        if relation in exposed:group='EXPOSED_ALIGNED'
        elif relation in control:group='CONTROL_PREDECLARED'
        else:
            rejected_relation+=1; continue
        x=copy.deepcopy(r); x['_group']=group; x['_p']=_ret(r,primary_h); x['_s']=_ret(r,secondary_h)
        eligible.append(x)

    matured=[r for r in eligible if r['_p'] is not None]
    ev=[r['_p'] for r in matured if r['_group']=='EXPOSED_ALIGNED']; cv=[r['_p'] for r in matured if r['_group']=='CONTROL_PREDECLARED']
    em=_metrics(ev); cm=_metrics(cv)
    dm=em['mean_pct']-cm['mean_pct'] if em['mean_pct'] is not None and cm['mean_pct'] is not None else None
    dp=em['positive_rate_pct']-cm['positive_rate_pct'] if em['positive_rate_pct'] is not None and cm['positive_rate_pct'] is not None else None

    posfolds=0; fold_reports=[]
    for i,fold in enumerate(_folds(eligible,int(rules['chronological_folds'])),1):
        fm=[r for r in fold if r['_p'] is not None]
        a=_metrics([r['_p'] for r in fm if r['_group']=='EXPOSED_ALIGNED']); b=_metrics([r['_p'] for r in fm if r['_group']=='CONTROL_PREDECLARED'])
        d=a['mean_pct']-b['mean_pct'] if a['mean_pct'] is not None and b['mean_pct'] is not None else None
        if d is not None and d>0:posfolds+=1
        fold_reports.append({'fold':i,'exposed':a,'control':b,'mean_delta_pct_points':round(d,6) if d is not None else None})

    blockers=[]
    min_e=int(rules['minimum_matured_exposed']); min_c=int(rules['minimum_matured_control'])
    if em['n']<min_e:blockers.append('EXPOSED_GROUP_BELOW_PREREGISTERED_MINIMUM')
    if cm['n']<min_c:blockers.append('CONTROL_GROUP_BELOW_PREREGISTERED_MINIMUM')
    th=rules['edge_claim_thresholds']; sample_ok=not blockers
    edge=bool(sample_ok and dm is not None and dm>=float(th['minimum_mean_return_delta_pct_points']) and dp is not None and dp>=float(th['minimum_positive_rate_delta_percentage_points']) and posfolds>=int(th['minimum_positive_mean_delta_folds']))

    sec_e=_metrics([r['_s'] for r in eligible if r['_group']=='EXPOSED_ALIGNED' and r['_s'] is not None]); sec_c=_metrics([r['_s'] for r in eligible if r['_group']=='CONTROL_PREDECLARED' and r['_s'] is not None])
    relation_counts={}
    for r in eligible:
        k=str(r.get('microstructure_relation_at_entry') or 'UNKNOWN'); relation_counts[k]=relation_counts.get(k,0)+1

    base.update({
        'status':'FORWARD_EDGE_SUPPORTED' if edge else 'FORWARD_EDGE_NOT_SUPPORTED' if sample_ok else 'COLLECTING_PREDECLARED_GROUP_SAMPLE',
        'blockers':blockers,'cohort_hash':man['cohort_hash'],'cohort_start_ms':start,'cohort_start_at':man['cohort_start_at'],
        'primary_horizon_h':primary_h,'secondary_descriptive_horizon_h':secondary_h,
        'eligible_forward_rows':len(eligible),'primary_matured_rows':len(matured),'pending_primary_rows':len(eligible)-len(matured),
        'rejected_precohort_rows':rejected_old,'rejected_missing_freeze_schema_rows':rejected_schema,'rejected_unclassified_relation_rows':rejected_relation,
        'relation_counts':relation_counts,
        'sample_progress':{
            'exposed_matured':em['n'],'exposed_target':min_e,'exposed_remaining':max(0,min_e-em['n']),
            'control_matured':cm['n'],'control_target':min_c,'control_remaining':max(0,min_c-cm['n']),
        },
        'primary':{
            'exposed_aligned':em,'control_predeclared':cm,
            'mean_return_delta_pct_points':round(dm,6) if dm is not None else None,
            'positive_rate_delta_percentage_points':round(dp,4) if dp is not None else None,
            'positive_mean_delta_folds':posfolds,'chronological_folds':fold_reports,'thresholds':copy.deepcopy(th),
        },
        'secondary_descriptive_only':{'exposed_aligned':sec_e,'control_predeclared':sec_c,'used_for_edge_claim':False},
        'primary_edge_claim':edge,
        'interpretation':'TRUE_FORWARD_DECISION_TIME_MICROSTRUCTURE_COHORT_RESEARCH_ONLY_NOT_TP_SL_R',
    })
    return base
