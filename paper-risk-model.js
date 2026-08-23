(function(){
  const nv=v=>{const x=Number(v);return Number.isFinite(x)?x:null;};
  function simulate(rows,riskPct,startEquity=10000){
    const settled=(rows||[]).filter(x=>['WIN','LOSS'].includes(String(x?.status||''))&&nv(x?.execution_model?.net_r)!=null).slice().sort((a,b)=>Number(a?.event_at_ms||a?.captured_at_ms||0)-Number(b?.event_at_ms||b?.captured_at_ms||0));
    let equity=startEquity,peak=startEquity,maxDD=0,maxDDCash=0,minEquity=startEquity;
    const curve=[{trade:0,equity,drawdown_pct:0}];
    settled.forEach((x,i)=>{const r=nv(x.execution_model.net_r)||0;const riskCash=equity*(riskPct/100);equity=Math.max(0,equity+r*riskCash);peak=Math.max(peak,equity);minEquity=Math.min(minEquity,equity);const ddCash=peak-equity,dd=peak>0?ddCash/peak*100:100;maxDD=Math.max(maxDD,dd);maxDDCash=Math.max(maxDDCash,ddCash);curve.push({trade:i+1,equity,drawdown_pct:dd,r,label:`${x.symbol||''} ${x.direction||''}`.trim()});});
    const ret=startEquity>0?(equity/startEquity-1)*100:null;const survival=equity>startEquity*.5?'SURVIVES':equity>0?'SEVERE_DRAWDOWN':'RUIN';
    return {risk_pct:riskPct,start_equity:startEquity,end_equity:equity,return_pct:ret,max_drawdown_pct:maxDD,max_drawdown_cash:maxDDCash,min_equity:minEquity,survival,trades:settled.length,curve};
  }
  function stress(portfolio){const n=Math.max(1,Number(portfolio?.max_loss_streak||0));return [0.25,0.5,1,2].map(r=>({risk_pct:r,loss_streak:n,approx_streak_drawdown_pct:(1-Math.pow(1-r/100,n))*100}));}
  window.ATLAS_PAPER_RISK={simulate,stress};
})();