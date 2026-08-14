const ATLAS_FINAL_RANKING_VERSION='5.4.0-alpha.6';
function frClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function frN(v,d=1){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function frEvidenceWeight(n){n=Number(n||0);if(n<10)return 0;if(n<30)return .20;if(n<100)return .45;if(n<200)return .70;return 1;}
function finalOpportunityRank({opportunity,futures=null,liquidity=null,similarity=null}={}){
 if(!opportunity)return {available:false,score:0,decision:'NO_DATA'};
 const dir=opportunity.direction==='LONG'?1:opportunity.direction==='SHORT'?-1:0;
 const base=Number(opportunity.score||50);
 let fut=50,liq=50,hist=50,hw=0;
 if(futures?.available){fut=frClamp(50+(dir?dir*Number(futures.score||0)*.5:0),0,100);}
 if(liquidity?.available)liq=frClamp(Number(liquidity.score||50),0,100);
 const h=similarity?.horizons?.['24']||{}, n=Number(h.n||0), hit=Number(h.hit_rate_pct), avg=Number(h.avg_directional_return_pct);
 if(n&&Number.isFinite(hit)&&Number.isFinite(avg)){hw=frEvidenceWeight(n);hist=frClamp(50+(hit-50)*.85+frClamp(avg*5,-15,15),0,100);}
 const fw=futures?.available?.10:0,lw=liquidity?.available?.08:0,hh=.14*hw,ow=.58;
 const used=ow+fw+lw+hh,neutral=Math.max(0,1-used);
 let score=base*ow+fut*fw+liq*lw+hist*hh+50*neutral;
 const blockers=[...(opportunity.blockers||[])], cautions=[...(opportunity.cautions||[])], confirmations=[...(opportunity.confirmations||[])];
 if(futures?.available){
   const conflict=(dir>0&&futures.bias==='BEARISH')||(dir<0&&futures.bias==='BULLISH');
   const aligned=(dir>0&&futures.bias==='BULLISH')||(dir<0&&futures.bias==='BEARISH');
   if(conflict){score-=6;cautions.push('FUTURES_CONFLICT');} if(aligned)confirmations.push('FUTURES_ALIGNED');
   if(futures.squeeze&&futures.squeeze!=='NONE')cautions.push(futures.squeeze);
 }
 if(liquidity?.available){if(liquidity.score<=35){score-=5;cautions.push('ADVERSE_LIQUIDITY');}else if(liquidity.score>=65)confirmations.push('LIQUIDITY_SUPPORTIVE');}
 if(hw>=.45&&hist>=65)confirmations.push('HISTORICAL_EDGE_POSITIVE');
 if(hw>=.45&&hist<=40){score-=7;cautions.push('HISTORICAL_EDGE_NEGATIVE');}
 if(!dir)blockers.push('NO_DIRECTION');
 score=Math.round(frClamp(score,0,100)); if(blockers.length)score=Math.min(score,54);
 let decision='NO_TRADE'; if(!blockers.length){if(score>=82)decision=dir>0?'LONG_CANDIDATE':'SHORT_CANDIDATE';else if(score>=70)decision=dir>0?'LONG_WATCH':'SHORT_WATCH';else if(score>=60)decision='WATCH';}
 return {available:true,version:ATLAS_FINAL_RANKING_VERSION,score,decision,direction:opportunity.direction,
   components:{opportunity:frN(base),futures:frN(fut),liquidity:frN(liq),historical:frN(hist)},
   weights:{opportunity:ow,futures:fw,liquidity:lw,historical:frN(hh,3),neutral:frN(neutral,3)},
   historical:{n,hit_rate_pct:Number.isFinite(hit)?hit:null,avg_directional_return_pct:Number.isFinite(avg)?avg:null,maturity_weight:hw},
   blockers:[...new Set(blockers)],cautions:[...new Set(cautions)],confirmations:[...new Set(confirmations)],
   research_only:true,live_execution:false};
}
window.ATLAS_FINAL_RANKING={finalOpportunityRank,version:ATLAS_FINAL_RANKING_VERSION};
