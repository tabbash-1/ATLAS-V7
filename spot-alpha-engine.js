
window.ATLAS_SPOT_ALPHA = (() => {
  const ema=(a,n)=>{let k=2/(n+1),v=a[0],o=[v];for(let i=1;i<a.length;i++){v=a[i]*k+v*(1-k);o.push(v)}return o};
  const ret=(a,n)=>a.length>n?(a.at(-1)/a.at(-1-n)-1)*100:null;
  const stdev=a=>{if(a.length<2)return 0;let m=a.reduce((x,y)=>x+y,0)/a.length;return Math.sqrt(a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1))};
  function features(candles){
    const c=candles.map(x=>+x.close), v=candles.map(x=>+x.volume);
    const e20=ema(c,20).at(-1), e50=ema(c,50).at(-1), px=c.at(-1);
    const r7=ret(c,7), r30=ret(c,30), r90=ret(c,90);
    const daily=[]; for(let i=Math.max(1,c.length-31);i<c.length;i++) daily.push((c[i]/c[i-1]-1)*100);
    const vol=stdev(daily);
    const v20=v.slice(-20).reduce((a,b)=>a+b,0)/Math.min(20,v.length);
    const vr=v20? v.at(-1)/v20:1;
    const trend=((px/e50)-1)*100;
    const quality=(e20>e50?1:-1)*Math.min(3,Math.abs(trend));
    return {price:px,r7,r30,r90,vol,volumeRatio:vr,trend,trendQuality:quality};
  }
  function score(f){
    // Transparent research baseline, not optimized: medium/long momentum + trend quality,
    // with volatility and turnover proxies penalized.
    let s=0;
    s += Math.max(-25,Math.min(25,(f.r30||0)*1.2));
    s += Math.max(-20,Math.min(20,(f.r90||0)*0.5));
    s += Math.max(-20,Math.min(20,(f.trendQuality||0)*7));
    s += Math.max(-10,Math.min(10,(f.volumeRatio-1)*8));
    s -= Math.max(0,(f.vol-4))*3;
    return Math.max(-100,Math.min(100,s));
  }
  function decision(s,costBps=20){
    // Edge proxy deliberately conservative until trained on forward returns.
    const rawEdge=Math.max(-3,Math.min(3,s/35));
    const friction=costBps/100;
    const net=rawEdge-friction;
    let action='WAIT', allocation=0;
    if(net>=1.2){action='BUY';allocation=Math.min(20,8+net*4)}
    else if(net>=0.5){action='ACCUMULATE';allocation=Math.min(12,4+net*3)}
    else if(net<=-0.8){action='EXIT / CASH';allocation=0}
    return {rawEdge,friction,net,action,allocation};
  }
  return {features,score,decision};
})();
