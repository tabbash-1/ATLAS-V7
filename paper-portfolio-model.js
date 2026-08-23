(function(){
  function n(v){const x=Number(v);return Number.isFinite(x)?x:null;}
  function analyze(rows){
    const settled=(rows||[]).filter(x=>['WIN','LOSS'].includes(String(x?.status||''))&&n(x?.execution_model?.net_r)!=null)
      .slice().sort((a,b)=>Number(a?.event_at_ms||a?.captured_at_ms||0)-Number(b?.event_at_ms||b?.captured_at_ms||0));
    let cumulativeR=0, peakR=0, maxDrawdownR=0, wins=0, losses=0, winStreak=0, lossStreak=0, maxWinStreak=0, maxLossStreak=0;
    const curve=[{trade:0,cumulative_r:0,drawdown_r:0,label:'START'}];
    settled.forEach((row,i)=>{
      const r=n(row.execution_model.net_r)||0; cumulativeR+=r; peakR=Math.max(peakR,cumulativeR);
      const dd=peakR-cumulativeR; maxDrawdownR=Math.max(maxDrawdownR,dd);
      if(r>0){wins++;winStreak++;lossStreak=0;maxWinStreak=Math.max(maxWinStreak,winStreak);}else if(r<0){losses++;lossStreak++;winStreak=0;maxLossStreak=Math.max(maxLossStreak,lossStreak);}
      curve.push({trade:i+1,cumulative_r:cumulativeR,drawdown_r:dd,label:`${row.symbol||''} ${row.direction||''}`.trim(),captured_at:row.captured_at,event_at_ms:row.event_at_ms});
    });
    const netRs=settled.map(x=>n(x.execution_model.net_r)).filter(x=>x!=null), ntr=netRs.length;
    const avgR=ntr?netRs.reduce((a,c)=>a+c,0)/ntr:null;
    const grossProfit=netRs.filter(x=>x>0).reduce((a,c)=>a+c,0), grossLoss=Math.abs(netRs.filter(x=>x<0).reduce((a,c)=>a+c,0));
    const profitFactor=grossLoss>0?grossProfit/grossLoss:(grossProfit>0?Infinity:null);
    return {trades:ntr,wins,losses,win_rate_pct:ntr?wins/ntr*100:null,cumulative_r:cumulativeR,avg_net_r:avgR,max_drawdown_r:maxDrawdownR,profit_factor:profitFactor,max_win_streak:maxWinStreak,max_loss_streak:maxLossStreak,curve};
  }
  window.ATLAS_PAPER_PORTFOLIO={analyze};
})();
