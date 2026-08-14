
const ATLAS_PORTFOLIO_RISK_VERSION='5.8.0-alpha.11';
function prClamp(v,a,b){return Math.max(a,Math.min(b,v));}
function prN(v,d=4){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function returns(candles,n=120){
  const xs=(candles||[]).slice(-(n+1));const out=[];
  for(let i=1;i<xs.length;i++){const a=Number(xs[i-1]?.close),b=Number(xs[i]?.close);if(a>0&&Number.isFinite(b))out.push(b/a-1);}
  return out;
}
function corr(a,b){
  const n=Math.min(a.length,b.length);if(n<20)return null;
  const x=a.slice(-n),y=b.slice(-n),mx=x.reduce((s,v)=>s+v,0)/n,my=y.reduce((s,v)=>s+v,0)/n;
  let num=0,dx=0,dy=0;for(let i=0;i<n;i++){const u=x[i]-mx,v=y[i]-my;num+=u*v;dx+=u*u;dy+=v*v;}
  return dx>0&&dy>0?num/Math.sqrt(dx*dy):null;
}
function correlationMatrix(assetSeries){
  const keys=Object.keys(assetSeries||{}),rets={};keys.forEach(k=>rets[k]=returns(assetSeries[k]));
  const matrix={};for(const a of keys){matrix[a]={};for(const b of keys){matrix[a][b]=a===b?1:prN(corr(rets[a],rets[b]),3);}}
  return {assets:keys,matrix};
}
function positionSize({equity,riskPct,entry,stop,leverage=1,maxNotionalPct=35}={}){
  const eq=Number(equity),rp=Number(riskPct),e=Number(entry),s=Number(stop),lev=Math.max(1,Number(leverage||1));
  if(!(eq>0&&rp>0&&e>0&&Number.isFinite(s)&&e!==s))return {available:false};
  const riskCash=eq*(rp/100),riskPerUnit=Math.abs(e-s),units=riskCash/riskPerUnit;
  let notional=units*e,cap=eq*(Number(maxNotionalPct||35)/100)*lev,capped=false;
  if(notional>cap){notional=cap;units=notional/e;capped=true;}
  const actualRisk=units*riskPerUnit;
  return {available:true,units:prN(units,8),notional:prN(notional,2),risk_cash:prN(actualRisk,2),risk_pct_of_equity:prN(100*actualRisk/eq,3),capped_by_notional:capped};
}
function assessPortfolio({candidate,openPositions=[],correlations=null,equity=10000,baseRiskPct=1,maxPortfolioRiskPct=4,maxCorrelatedRiskPct=2.25}={}){
  const dir=String(candidate?.direction||'NONE'),sym=String(candidate?.symbol||'UNKNOWN');
  const blockers=[],cautions=[],confirmations=[];
  const openRisk=openPositions.reduce((s,p)=>s+Number(p.risk_pct||0),0);
  let correlatedRisk=0,maxCorr=0,cluster=[];
  const candSign=dir==='LONG'?1:dir==='SHORT'?-1:0;
  for(const p of openPositions){
    const c=Number(correlations?.[sym]?.[p.symbol]),posSign=p.direction==='LONG'?1:p.direction==='SHORT'?-1:0;
    if(Number.isFinite(c)){
      const effective=c*candSign*posSign;
      maxCorr=Math.max(maxCorr,effective);
      if(effective>=.70){correlatedRisk+=Number(p.risk_pct||0);cluster.push({symbol:p.symbol,correlation:prN(c,2),effective_correlation:prN(effective,2),direction:p.direction,risk_pct:Number(p.risk_pct||0)});}
    }
  }
  let suggested=Number(baseRiskPct||1);
  if(maxCorr>=.85){suggested*=.45;cautions.push('VERY_HIGH_CORRELATION_CLUSTER');}
  else if(maxCorr>=.70){suggested*=.65;cautions.push('HIGH_CORRELATION_CLUSTER');}
  if(openRisk>=Number(maxPortfolioRiskPct||4)*.75){suggested*=.6;cautions.push('PORTFOLIO_RISK_NEAR_LIMIT');}
  if(correlatedRisk>=Number(maxCorrelatedRiskPct||2.25)){suggested*=.5;cautions.push('CORRELATED_RISK_LIMIT_NEAR_OR_EXCEEDED');}
  const remaining=Math.max(0,Number(maxPortfolioRiskPct||4)-openRisk);
  suggested=Math.min(suggested,remaining);
  if(remaining<=0){blockers.push('PORTFOLIO_RISK_LIMIT_REACHED');suggested=0;}
  if(correlatedRisk>=Number(maxCorrelatedRiskPct||2.25)&&maxCorr>=.85&&openPositions.length){blockers.push('CORRELATED_CLUSTER_BLOCK');suggested=0;}
  if(suggested>=Number(baseRiskPct||1)*.9)confirmations.push('FULL_BASE_RISK_AVAILABLE');
  return {version:ATLAS_PORTFOLIO_RISK_VERSION,symbol:sym,direction:dir,open_portfolio_risk_pct:prN(openRisk,2),
    correlated_risk_pct:prN(correlatedRisk,2),max_effective_correlation:prN(maxCorr,2),correlation_cluster:cluster,
    base_risk_pct:Number(baseRiskPct||1),suggested_risk_pct:prN(Math.max(0,suggested),3),remaining_portfolio_risk_pct:prN(remaining,2),
    blockers,cautions,confirmations,research_only:true,live_execution:false};
}
window.ATLAS_PORTFOLIO_RISK={returns,corr,correlationMatrix,positionSize,assessPortfolio,version:ATLAS_PORTFOLIO_RISK_VERSION};
