const ATLAS_DECISION_QUALITY_VERSION='1.0.0';
function aqClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function aqNum(v){return Number.isFinite(+v)?+v:null;}
function aqSide(x){const s=String(x||'').toUpperCase();if(/LONG|BUY|BULL/.test(s))return 1;if(/SHORT|SELL|BEAR/.test(s))return -1;return 0;}
function atlasDecisionQuality(packet,thesis){
  const mt=packet?.multi_timeframe||{}; const tfs=mt.timeframes||{}; const names=Object.keys(tfs);
  const expected=['1W','1D','12H','6H','4H','1H','30M','15M'];
  const completeness=names.length/expected.length;
  const sides=[]; for(const tf of names){const m=tfs[tf]?.market||{};let s=aqSide(m.signal); if(!s)s=aqSide(m.engine?.trend); if(s)sides.push(s);}
  const agreement=sides.length?Math.abs(sides.reduce((a,b)=>a+b,0))/sides.length:0;
  const ev=packet?.evidence||{}; const evidenceKeys=['smart_money','futures','liquidity','confluence','master_conviction','pattern_memory','news','event_intelligence','portfolio_risk'];
  const present=evidenceKeys.filter(k=>ev[k]!=null); const evidenceCompleteness=present.length/evidenceKeys.length;
  const evidenceSides=[];
  for(const k of present){const v=ev[k]||{}; const s=aqSide(v.decision||v.signal||v.bias||v.alignment||v.direction); if(s)evidenceSides.push(s);}
  const evidenceAgreement=evidenceSides.length?Math.abs(evidenceSides.reduce((a,b)=>a+b,0))/evidenceSides.length:.5;
  const missingCritical=[]; if(!tfs['1D'])missingCritical.push('1D'); if(!tfs['4H'])missingCritical.push('4H'); if(!tfs['1H'])missingCritical.push('1H');
  if(!ev.master_conviction)missingCritical.push('master_conviction'); if(!ev.liquidity)missingCritical.push('liquidity');
  let score=(completeness*.28)+(agreement*.27)+(evidenceCompleteness*.20)+(evidenceAgreement*.15)+((1-Math.min(1,missingCritical.length/5))*.10);
  score=aqClamp(score,0,1); const quality=Math.round(score*100);
  let gate='PASS'; const reasons=[];
  if(names.length<3){gate='BLOCK';reasons.push('Fewer than 3 usable timeframes');}
  if(missingCritical.includes('1D')&&missingCritical.includes('4H')){gate='BLOCK';reasons.push('Higher-timeframe structure missing');}
  if(agreement<.35&&sides.length>=3){gate='BLOCK';reasons.push('Strong timeframe conflict');}
  if(quality<55){gate='BLOCK';reasons.push('Decision quality below 55');}
  else if(quality<70&&gate!=='BLOCK'){gate='CAUTION';reasons.push('Decision quality below 70');}
  const direction=aqSide(thesis?.decision); if(direction&&sides.length>=3){const net=Math.sign(sides.reduce((a,b)=>a+b,0)); if(net&&net!==direction){gate='BLOCK';reasons.push('Proposed trade opposes timeframe majority');}}
  const maxConfidence=gate==='BLOCK'?49:gate==='CAUTION'?69:quality>=85?92:84;
  return {version:ATLAS_DECISION_QUALITY_VERSION,quality_score:quality,gate,max_confidence:maxConfidence,timeframe_completeness:+completeness.toFixed(3),timeframe_agreement:+agreement.toFixed(3),evidence_completeness:+evidenceCompleteness.toFixed(3),evidence_agreement:+evidenceAgreement.toFixed(3),missing_critical:missingCritical,reasons};
}
function atlasApplyDecisionGate(packet,thesis){const q=atlasDecisionQuality(packet,thesis);const out={...thesis,decision_quality:q};out.confidence=Math.min(Number(out.confidence)||0,q.max_confidence);if(q.gate==='BLOCK'&&out.decision!=='WAIT'){out.original_decision=out.decision;out.decision='WAIT';out.no_trade_reason=['Quality gate blocked trade',...(q.reasons||[])].join(': ');out.stop_loss=null;out.take_profit_1=null;out.take_profit_2=null;out.take_profit_3=null;out.risk_reward=null;}return out;}
if(typeof window!=='undefined')window.ATLAS_DECISION_QUALITY={version:ATLAS_DECISION_QUALITY_VERSION,atlasDecisionQuality,atlasApplyDecisionGate};
