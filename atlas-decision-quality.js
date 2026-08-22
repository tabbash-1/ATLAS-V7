const ATLAS_DECISION_QUALITY_VERSION='1.1.0';
function aqClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function aqSide(x){const s=String(x||'').toUpperCase();if(/LONG|BUY|BULL/.test(s))return 1;if(/SHORT|SELL|BEAR/.test(s))return -1;return 0;}
function atlasDecisionQuality(packet,thesis){
  const mt=packet?.multi_timeframe||{},tfs=mt.timeframes||{},names=Object.keys(tfs),expected=['1W','1D','12H','6H','4H','1H','30M','15M'];
  const completeness=names.length/expected.length,sides=names.map(tf=>aqSide(tfs[tf]?.market?.signal)||aqSide(tfs[tf]?.market?.engine?.trend)).filter(Boolean),agreement=sides.length?Math.abs(sides.reduce((a,b)=>a+b,0))/sides.length:0;
  const ev=packet?.evidence||{},evidenceKeys=['smart_money','futures','liquidity','confluence','master_conviction','pattern_memory','news','event_intelligence','portfolio_risk'],present=evidenceKeys.filter(k=>ev[k]!=null),evidenceCompleteness=present.length/evidenceKeys.length;
  const evidenceSides=present.map(k=>aqSide(ev[k]?.decision||ev[k]?.signal||ev[k]?.bias||ev[k]?.alignment||ev[k]?.direction)).filter(Boolean),evidenceAgreement=evidenceSides.length?Math.abs(evidenceSides.reduce((a,b)=>a+b,0))/evidenceSides.length:.5;
  const missingCritical=[];if(!tfs['1D'])missingCritical.push('1D');if(!tfs['4H'])missingCritical.push('4H');if(!tfs['1H'])missingCritical.push('1H');if(!ev.master_conviction)missingCritical.push('master_conviction');if(!ev.liquidity)missingCritical.push('liquidity');
  let score=(completeness*.23)+(agreement*.22)+(evidenceCompleteness*.16)+(evidenceAgreement*.12)+((1-Math.min(1,missingCritical.length/5))*.09);
  const htfSide=aqSide(mt.higher_timeframe_bias),ltfSide=aqSide(mt.entry_timing_bias),direction=aqSide(thesis?.decision);const alignment=htfSide&&ltfSide?(htfSide===ltfSide?1:.25):.5;score+=alignment*.18;
  score=aqClamp(score,0,1);const quality=Math.round(score*100),rr=Number.isFinite(+thesis?.risk_reward)?+thesis.risk_reward:null,sl=Number(thesis?.stop_loss),tp1=Number(thesis?.take_profit_1),entry=Array.isArray(thesis?.entry_zone)?Number(thesis.entry_zone[direction>0?1:0]):null;
  let gate='PASS';const reasons=[];
  if(names.length<3){gate='BLOCK';reasons.push('Fewer than 3 usable timeframes');}
  if(missingCritical.includes('1D')&&missingCritical.includes('4H')){gate='BLOCK';reasons.push('Higher-timeframe structure missing');}
  if(agreement<.35&&sides.length>=3){gate='BLOCK';reasons.push('Strong timeframe conflict');}
  if(direction&&htfSide&&direction!==htfSide){gate='BLOCK';reasons.push('Trade opposes higher-timeframe bias');}
  if(direction&&rr!=null&&rr<1){gate='BLOCK';reasons.push('Risk/reward below 1.0');}
  if(direction&&(!Number.isFinite(sl)||!Number.isFinite(tp1)||!Number.isFinite(entry))){gate='BLOCK';reasons.push('Incomplete trade geometry');}
  if(direction&&Number.isFinite(sl)&&Number.isFinite(entry)&&((direction>0&&sl>=entry)||(direction<0&&sl<=entry))){gate='BLOCK';reasons.push('Invalid stop-loss geometry');}
  if(direction&&Number.isFinite(tp1)&&Number.isFinite(entry)&&((direction>0&&tp1<=entry)||(direction<0&&tp1>=entry))){gate='BLOCK';reasons.push('Invalid target geometry');}
  if(quality<55){gate='BLOCK';reasons.push('Decision quality below 55');}else if(quality<70&&gate!=='BLOCK'){gate='CAUTION';reasons.push('Decision quality below 70');}
  if(direction&&sides.length>=3){const net=Math.sign(sides.reduce((a,b)=>a+b,0));if(net&&net!==direction){gate='BLOCK';reasons.push('Proposed trade opposes timeframe majority');}}
  const maxConfidence=gate==='BLOCK'?49:gate==='CAUTION'?69:quality>=85?92:84;
  return{version:ATLAS_DECISION_QUALITY_VERSION,quality_score:quality,gate,max_confidence:maxConfidence,timeframe_completeness:+completeness.toFixed(3),timeframe_agreement:+agreement.toFixed(3),higher_timeframe_bias:mt.higher_timeframe_bias||'UNKNOWN',entry_timing_bias:mt.entry_timing_bias||'UNKNOWN',htf_ltf_alignment:+alignment.toFixed(3),evidence_completeness:+evidenceCompleteness.toFixed(3),evidence_agreement:+evidenceAgreement.toFixed(3),risk_reward:rr,missing_critical:missingCritical,reasons};
}
function atlasApplyDecisionGate(packet,thesis){const q=atlasDecisionQuality(packet,thesis),out={...thesis,decision_quality:q};out.confidence=Math.min(Number(out.confidence)||0,q.max_confidence);if(q.gate==='BLOCK'&&out.decision!=='WAIT'){out.original_decision=out.decision;out.decision='WAIT';out.no_trade_reason=['Quality gate blocked trade',...(q.reasons||[])].join(': ');out.entry_zone=null;out.invalidation=null;out.stop_loss=null;out.take_profit_1=null;out.take_profit_2=null;out.take_profit_3=null;out.risk_reward=null;}return out;}
if(typeof window!=='undefined')window.ATLAS_DECISION_QUALITY={version:ATLAS_DECISION_QUALITY_VERSION,atlasDecisionQuality,atlasApplyDecisionGate};
