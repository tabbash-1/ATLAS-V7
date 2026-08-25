"""ATLAS Decision Engine V10: continuation-aware geometry + explicit opportunity states."""

import production_signal_scoring as scoring
import futures_provider_chain
import production_trade_plan

VERSION = 'DECISION_ENGINE_V10_OPPORTUNITY_STATE'


def opportunity_state(direction, qualified, execution_ready, plan_status=None):
    """Classify setup maturity without weakening Production qualification.

    ACTIONABLE = qualified and executable now.
    ARMED      = qualified direction with a complete conditional Production plan.
    WATCH      = directional candidate that has not cleared Production qualification.
    NO_SETUP   = no directional candidate.
    """
    if direction not in ('LONG', 'SHORT'):
        return 'NO_SETUP'
    if execution_ready:
        return 'ACTIONABLE'
    if qualified and plan_status == 'CONDITIONAL':
        return 'ARMED'
    return 'WATCH'


def install(atlas):
    futures_provider_chain.install(atlas)
    original = atlas.production_decision

    def build(symbol):
        result = original(symbol)
        if not isinstance(result, dict) or not result.get('ok'):
            return result
        sym=str(result.get('symbol') or symbol or '').upper().replace('BINANCE:','')
        direction=result.get('candidate_direction'); px=atlas.fnum(result.get('entry'))
        indicators=result.get('indicators') or {}; atr=atlas.fnum(indicators.get('atr14'))
        votes=int(result.get('direction_votes') or 0); mom24=atlas.fnum(indicators.get('momentum_24h_pct'),0) or 0
        paced_rv=atlas.fnum(result.get('relative_volume'),0) or 0; attr=result.get('score_attribution') or {}
        momentum_adj=atlas.fnum(attr.get('momentum_adjustment'),0) or 0; breadth_adj=atlas.fnum(attr.get('market_breadth_adjustment'),0) or 0
        guard_adj=atlas.fnum(attr.get('extension_guard_adjustment'),0) or 0
        continuation_strong=bool(votes==4 and momentum_adj>=4 and breadth_adj>=2 and guard_adj>=0)
        if direction in ('LONG','SHORT') and px and atr and atr>0:
            ks=atlas._spot_klines(sym); level,distance,source=scoring.structural_obstacle(ks,px,direction)
            breakout=scoring.breakout_context(ks,px,direction,votes,mom24,atr,paced_rv); extension=1.6 if breakout.get('confirmed') else 1.4
            target=level; target_source=source
            if continuation_strong and level is not None and distance is not None and distance<=1.5:
                target=level+atr*1.4 if direction=='LONG' else level-atr*1.4; target_source='CONTINUATION_EXTENSION_BEYOND_PRIOR_STRUCTURE'
            elif target is None:
                target=px+atr*extension if direction=='LONG' else px-atr*extension; target_source='ATR_EXTENSION_AFTER_CLEAR_STRUCTURE'
            stop=px-atr*1.2 if direction=='LONG' else px+atr*1.2; risk=abs(px-stop)
            reward=(target-px) if direction=='LONG' else (px-target); rr=reward/risk if risk>0 and reward>0 else None
            directional=bool(rr is not None and ((direction=='LONG' and stop<px<target) or (direction=='SHORT' and target<px<stop)))
            geometry_ok=bool(directional and rr>=1.0); qualified=bool(result.get('production_signal_qualified'))
            result.update({'stop_loss':round(stop,10),'take_profit':round(target,10),'risk_reward':round(rr,3) if rr is not None else None})
            result['structural_geometry']={'source':target_source,'obstacle_price':round(level,10) if level is not None else None,'obstacle_distance_pct':round(distance,3) if distance is not None else None,'breakout':breakout,'continuation_strong':continuation_strong,'continuation_target_extended':target_source=='CONTINUATION_EXTENSION_BEYOND_PRIOR_STRUCTURE','uses_current_candle_as_obstacle':False}
            result['geometry_gate']={'status':'PASS' if geometry_ok else 'BLOCK','qualified':geometry_ok,'reason':'RR_ONE_TO_ONE_OR_BETTER' if geometry_ok else 'RR_BELOW_ONE_TO_ONE' if rr is not None else 'GEOMETRY_INCOMPLETE','min_risk_reward':1.0,'risk_reward':round(rr,6) if rr is not None else None}
            result['execution_ready']=bool(qualified and geometry_ok); result['actionable_decision']=direction if result['execution_ready'] else 'WAIT'
            result['actionable_reason']='EXECUTION_READY_CONTINUATION_AWARE' if result['execution_ready'] and continuation_strong else 'EXECUTION_READY_BREAKOUT_AWARE' if result['execution_ready'] else result['geometry_gate']['reason'] if qualified else result.get('wait_reason')
            result['trade_plan_status']='EXECUTION_READY' if result['execution_ready'] else 'SCORE_QUALIFIED_GEOMETRY_BLOCKED' if qualified else result.get('trade_plan_status')
            matrix=result.get('timeframe_matrix') or {}; swing=matrix.get('swing') or {}; swing.update({'risk_reward':result['risk_reward'],'execution_ready':result['execution_ready'],'actionable_decision':result['actionable_decision'],'structural_target_source':target_source,'breakout_confirmed':bool(breakout.get('confirmed')),'continuation_strong':continuation_strong}); matrix['swing']=swing; result['timeframe_matrix']=matrix
        result['trade_plan']=production_trade_plan.build(result)
        plan=result['trade_plan']
        qualified=bool(result.get('production_signal_qualified'))
        state=opportunity_state(result.get('candidate_direction'), qualified, bool(result.get('execution_ready')), plan.get('status'))
        result['opportunity_state']=state
        result['opportunity_state_reason']=(
            'QUALIFIED_AND_EXECUTABLE_NOW' if state=='ACTIONABLE' else
            'QUALIFIED_WITH_CONDITIONAL_ENTRY_PLAN' if state=='ARMED' else
            'DIRECTIONAL_CANDIDATE_NOT_YET_PRODUCTION_QUALIFIED' if state=='WATCH' else
            'NO_DIRECTIONAL_CANDIDATE'
        )
        matrix=result.get('timeframe_matrix') or {}; swing=matrix.get('swing') or {}; swing['opportunity_state']=state; matrix['swing']=swing; result['timeframe_matrix']=matrix
        lane='PRODUCTION_SWING' if state=='ACTIONABLE' else 'ARMED_PRODUCTION' if state=='ARMED' else 'WATCH_PRODUCTION' if state=='WATCH' else 'NO_SETUP'
        result['best_available_action']={'action':plan.get('action'),'direction':plan.get('direction'),'lane':lane,'status':plan.get('status'),'opportunity_state':state,'entry_mode':plan.get('entry_mode'),'entry':plan.get('entry'),'entry_trigger':plan.get('entry_trigger'),'stop_loss':plan.get('stop_loss'),'tp1':plan.get('tp1'),'tp2':plan.get('tp2'),'rr_tp1':plan.get('rr_tp1'),'rr_tp2':plan.get('rr_tp2'),'can_execute':False,'research_only':True}
        result['decision_engine_version']=VERSION
        return result
    atlas.production_decision=build
    atlas.DECISION_ENGINE_V7_STATE={'enabled':True,'version':VERSION,'production_threshold_unchanged':True,'futures_provider_chain':futures_provider_chain.VERSION,'continuation_aware':True,'complete_trade_plan':True,'explicit_opportunity_states':['ACTIONABLE','ARMED','WATCH','NO_SETUP']}
    return atlas.DECISION_ENGINE_V7_STATE
