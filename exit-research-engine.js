
const ATLAS_EXIT_LAB_VERSION='5.7.0-alpha.10';
function xlN(v,d=3){return Number.isFinite(Number(v))?Number(Number(v).toFixed(d)):null;}
function touched(c,px,dir,isTarget){
  if(dir>0)return isTarget?c.high>=px:c.low<=px;
  return isTarget?c.low<=px:c.high>=px;
}
function simulateFixed(future,entry,atr,dir,maxBars=24){
  const stop=entry-dir*1.5*atr,target=entry+dir*3*atr,risk=1.5*atr;
  for(let i=0;i<Math.min(maxBars,future.length);i++){
    const c=future[i],s=touched(c,stop,dir,false),t=touched(c,target,dir,true);
    if(s&&t)return {r:-1,bars:i+1,outcome:'STOP_AMBIGUOUS_SAME_BAR'};
    if(s)return {r:-1,bars:i+1,outcome:'STOP'};
    if(t)return {r:2,bars:i+1,outcome:'TARGET'};
  }
  const last=future[Math.min(maxBars,future.length)-1];if(!last)return {r:0,bars:0,outcome:'NO_FUTURE'};
  return {r:dir*(last.close-entry)/risk,bars:Math.min(maxBars,future.length),outcome:'TIME_EXIT'};
}
function simulateManaged(future,plan,dir,maxBars=24){
  const entry=plan.entry,stop=plan.stop,tp1=plan.tp1,tp2=plan.tp2,risk=plan.risk_per_unit;
  let partial=false,realized=0,remaining=1,currentStop=stop;
  for(let i=0;i<Math.min(maxBars,future.length);i++){
    const c=future[i];
    const stopHit=touched(c,currentStop,dir,false),t1=!partial&&touched(c,tp1,dir,true),t2=touched(c,tp2,dir,true);
    if(!partial){
      if(stopHit&&(t1||t2))return {r:-1,bars:i+1,outcome:'STOP_AMBIGUOUS_SAME_BAR'};
      if(stopHit)return {r:-1,bars:i+1,outcome:'STOP'};
      if(t1||t2){
        const rr1=Math.abs(tp1-entry)/risk; realized=.4*rr1;remaining=.6;partial=true;currentStop=entry;
        if(t2){const rr2=Math.abs(tp2-entry)/risk;return {r:realized+remaining*rr2,bars:i+1,outcome:'TP1_TP2'};}
      }
    }else{
      if(stopHit&&t2)return {r:realized,bars:i+1,outcome:'BE_THEN_TP2_AMBIGUOUS'};
      if(stopHit)return {r:realized,bars:i+1,outcome:'TP1_THEN_BE'};
      if(t2){const rr2=Math.abs(tp2-entry)/risk;return {r:realized+remaining*rr2,bars:i+1,outcome:'TP1_TP2'};}
      // Simple validated-later ATR trail after TP1 using candle close.
      const trail=c.close-dir*1.2*(risk/1.5);
      if(dir>0)currentStop=Math.max(currentStop,trail);else currentStop=Math.min(currentStop,trail);
    }
  }
  const last=future[Math.min(maxBars,future.length)-1];if(!last)return {r:realized,bars:0,outcome:'NO_FUTURE'};
  return {r:realized+remaining*dir*(last.close-entry)/risk,bars:Math.min(maxBars,future.length),outcome:partial?'TP1_TIME_EXIT':'TIME_EXIT'};
}
function summarize(trades){
  if(!trades.length)return {n:0,avg_r:null,win_rate_pct:null,total_r:0,max_loss_streak:0};
  const vals=trades.map(x=>x.r),wins=vals.filter(x=>x>0).length;
  let streak=0,maxStreak=0;for(const v of vals){if(v<=0){streak++;maxStreak=Math.max(maxStreak,streak);}else streak=0;}
  return {n:vals.length,avg_r:xlN(vals.reduce((a,b)=>a+b,0)/vals.length),win_rate_pct:xlN(100*wins/vals.length,1),
    total_r:xlN(vals.reduce((a,b)=>a+b,0)),max_loss_streak:maxStreak};
}
function runExitResearch(candles,{step=4,maxBars=24,costBps=20}={}){
  const fixed=[],managed=[],samples=[];
  for(let i=90;i<candles.length-maxBars;i+=step){
    const hist=candles.slice(0,i+1),base=analyzeMarket(hist);if(!['BUY','SELL'].includes(base.signal))continue;
    const con=analyzeAtlasConfluence(hist,base);if(con.gate?.state==='BLOCK')continue;
    const plan=ATLAS_TRADE_MANAGEMENT.buildTradePlan({base,confluence:con});
    if(!plan.available||plan.status==='NO_TRADE_RISK_GEOMETRY')continue;
    const dir=base.signal==='BUY'?1:-1,atr=Number(base.indicators?.atr14),future=candles.slice(i+1,i+1+maxBars);
    const a=simulateFixed(future,base.entry,atr,dir,maxBars),b=simulateManaged(future,plan,dir,maxBars);
    const fixedRisk=1.5*atr,managedRisk=Number(plan.risk_per_unit||fixedRisk);
    const costFrac=Number(costBps||0)/10000;
    const fixedCostR=costFrac*Number(base.entry)/fixedRisk,managedCostR=costFrac*Number(base.entry)/managedRisk;
    a.r-=fixedCostR;b.r-=managedCostR;a.cost_r=fixedCostR;b.cost_r=managedCostR;
    fixed.push(a);managed.push(b);samples.push({time:candles[i].time,signal:base.signal,fixed_r:xlN(a.r),managed_r:xlN(b.r),plan_status:plan.status,rr1:plan.rr_tp1,rr2:plan.rr_tp2});
  }
  const fs=summarize(fixed),ms=summarize(managed);
  return {version:ATLAS_EXIT_LAB_VERSION,trades:samples.length,fixed_atr:fs,sr_managed:ms,
    delta:{avg_r:xlN((ms.avg_r||0)-(fs.avg_r||0)),win_rate_pct:xlN((ms.win_rate_pct||0)-(fs.win_rate_pct||0),1),total_r:xlN((ms.total_r||0)-(fs.total_r||0))},
    cost_bps:Number(costBps||0),samples:samples.slice(-50),methodology:`Walk-forward-like sequential signal snapshots; conservative same-bar stop priority; ${costBps} bps round-trip cost proxy included.`,research_only:true,live_execution:false};
}
window.ATLAS_EXIT_LAB={runExitResearch,version:ATLAS_EXIT_LAB_VERSION};
