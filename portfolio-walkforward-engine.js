
window.ATLAS_PORTFOLIO_WF = (() => {
  function mean(a){return a.length?a.reduce((x,y)=>x+y,0)/a.length:0}
  function stdev(a){if(a.length<2)return 0;const m=mean(a);return Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1))}
  function ema(arr,n){if(!arr.length)return[];const k=2/(n+1);let v=arr[0],o=[v];for(let i=1;i<arr.length;i++){v=arr[i]*k+v*(1-k);o.push(v)}return o}
  function ret(arr,n,i){return i>=n?(arr[i]/arr[i-n]-1)*100:null}
  function maxDrawdown(eq){
    let peak=eq[0]||1,mdd=0;
    for(const x of eq){if(x>peak)peak=x;const d=(peak-x)/peak;if(d>mdd)mdd=d}
    return mdd*100;
  }
  function dailySharpe(rets){
    if(rets.length<2)return 0;
    const m=mean(rets),s=stdev(rets);
    return s? (m/s)*Math.sqrt(365):0;
  }
  function cagr(start,end,days){
    if(start<=0||end<=0||days<=0)return 0;
    return (Math.pow(end/start,365/days)-1)*100;
  }
  function features(series,i){
    const closes=series.map(x=>x.close), vols=series.map(x=>x.volume);
    if(i<100)return null;
    const e20=ema(closes.slice(0,i+1),20).at(-1);
    const e50=ema(closes.slice(0,i+1),50).at(-1);
    const px=closes[i];
    const r30=ret(closes,30,i), r90=ret(closes,90,i);
    const dr=[];
    for(let j=i-29;j<=i;j++) if(j>0) dr.push((closes[j]/closes[j-1]-1)*100);
    const vol=stdev(dr);
    const v20=mean(vols.slice(i-19,i+1));
    const vr=v20?vols[i]/v20:1;
    const trend=((px/e50)-1)*100;
    const tq=(e20>e50?1:-1)*Math.min(3,Math.abs(trend));
    return {r30,r90,vol,volumeRatio:vr,trend,trendQuality:tq};
  }
  function alphaScore(f){
    let s=0;
    s += Math.max(-25,Math.min(25,(f.r30||0)*1.2));
    s += Math.max(-20,Math.min(20,(f.r90||0)*0.5));
    s += Math.max(-20,Math.min(20,(f.trendQuality||0)*7));
    s += Math.max(-10,Math.min(10,(f.volumeRatio-1)*8));
    s -= Math.max(0,(f.vol-4))*3;
    return Math.max(-100,Math.min(100,s));
  }
  function simulate(data,opts={}){
    const capital=+opts.capital||10000;
    const topN=Math.max(1,+opts.topN||2);
    const rebalanceDays=Math.max(1,+opts.rebalanceDays||7);
    const roundTripBps=Math.max(0,+opts.roundTripBps||20);
    const minScore=+opts.minScore||15;
    const maxAssetWeight=Math.min(1,Math.max(.05,(+opts.maxAssetWeightPct||50)/100));
    const symbols=Object.keys(data);
    if(!symbols.length) throw new Error('No history');
    // Intersection by open-time to ensure contemporaneous comparison.
    const maps={}; for(const s of symbols)maps[s]=new Map(data[s].map(x=>[x.time,x]));
    let times=data[symbols[0]].map(x=>x.time).filter(t=>symbols.every(s=>maps[s].has(t))).sort((a,b)=>a-b);
    if(times.length<160)throw new Error('Not enough common history');
    const aligned={};
    for(const s of symbols) aligned[s]=times.map(t=>maps[s].get(t));
    let equity=capital,cash=capital,holdings={},weights={},eq=[capital],dailyRets=[],turnover=0,feesPaid=0,rebalances=0,cashDays=0;
    const logs=[];
    let startIdx=100;
    // Start after enough lookback. Scores at t, execution at t+1 open.
    for(let i=startIdx;i<times.length-1;i++){
      const doReb=((i-startIdx)%rebalanceDays===0);
      if(doReb){
        const ranked=[];
        for(const s of symbols){
          const f=features(aligned[s],i); if(!f)continue;
          const sc=alphaScore(f);
          ranked.push({symbol:s,score:sc,features:f});
        }
        ranked.sort((a,b)=>b.score-a.score);
        const chosen=ranked.filter(x=>x.score>=minScore).slice(0,topN);
        let target={};
        if(chosen.length){
          const w=Math.min(maxAssetWeight,1/chosen.length);
          for(const x of chosen) target[x.symbol]=w;
          // leftover remains cash if cap prevents full allocation.
        }
        // Portfolio value at next open before rebalance.
        const openVal=Object.entries(holdings).reduce((v,[s,q])=>v+q*aligned[s][i+1].open,cash);
        let targetInvested=Object.values(target).reduce((a,b)=>a+b,0);
        let turnoverFrac=0;
        for(const s of symbols){
          const curr=((holdings[s]||0)*aligned[s][i+1].open)/(openVal||1);
          const tw=target[s]||0; turnoverFrac+=Math.abs(tw-curr);
        }
        // One-way traded notional approximation is half L1 weight change; charge half round-trip bps on traded notional.
        const tradedFrac=turnoverFrac/2;
        const fee=openVal*tradedFrac*(roundTripBps/20000);
        feesPaid+=fee; turnover+=tradedFrac; equity=openVal-fee;
        holdings={}; cash=equity*(1-targetInvested);
        for(const [s,w] of Object.entries(target)) holdings[s]=(equity*w)/aligned[s][i+1].open;
        weights=target; rebalances++;
        logs.push({signal_time:times[i],execution_time:times[i+1],equity_before:openVal,fee,ranked:ranked.slice(0,5).map(x=>({symbol:x.symbol,score:+x.score.toFixed(2)})),selected:Object.keys(target)});
      }
      // Mark from current close to next close after any rebalance at next open.
      const before=equity;
      equity=cash+Object.entries(holdings).reduce((v,[s,q])=>v+q*aligned[s][i+1].close,cash*0);
      const r=before?equity/before-1:0; dailyRets.push(r); eq.push(equity);
      if(!Object.keys(holdings).length)cashDays++;
      // carry cash based on holdings valuation
      cash = equity - Object.entries(holdings).reduce((v,[s,q])=>v+q*aligned[s][i+1].close,0);
    }
    const days=(times.at(-1)-times[startIdx])/(86400000);
    const btc=aligned['BTCUSDT'];
    let btcStart=btc?btc[startIdx+1].open:null, btcEnd=btc?btc.at(-1).close:null;
    const btcRet=btcStart&&btcEnd?(btcEnd/btcStart-1)*100:null;
    const btcEq=btcStart?times.slice(startIdx+1).map((t,k)=>capital*(btc[startIdx+1+k].close/btcStart)):[];
    return {
      schema:'ATLAS_SPOT_WF_V1',research_only:true,live_execution:false,
      period:{start:new Date(times[startIdx]).toISOString(),end:new Date(times.at(-1)).toISOString(),days:Math.round(days),common_candles:times.length},
      config:{capital,topN,rebalanceDays,roundTripBps,minScore,maxAssetWeightPct:maxAssetWeight*100},
      metrics:{
        finalEquity:+equity.toFixed(2),netReturnPct:+((equity/capital-1)*100).toFixed(2),cagrPct:+cagr(capital,equity,days).toFixed(2),
        maxDrawdownPct:+maxDrawdown(eq).toFixed(2),sharpe:+dailySharpe(dailyRets).toFixed(2),
        feesPaid:+feesPaid.toFixed(2),turnoverX:+turnover.toFixed(2),rebalances,cashDayPct:+(cashDays/Math.max(1,dailyRets.length)*100).toFixed(1),
        btcBuyHoldReturnPct:btcRet==null?null:+btcRet.toFixed(2),btcMaxDrawdownPct:btcEq.length?+maxDrawdown(btcEq).toFixed(2):null,
        alphaVsBtcPct:btcRet==null?null:+(((equity/capital-1)*100)-btcRet).toFixed(2)
      },
      equityCurve:eq, logs
    };
  }
  return {simulate,alphaScore,features};
})();
