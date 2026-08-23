(function(){
  const $=id=>document.getElementById(id);
  const SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT'];
  const HORIZONS=[1,4,12,24];
  const num=v=>v==null||!Number.isFinite(Number(v))?null:Number(v);
  const fmt=(v,d=2)=>num(v)==null?'—':num(v).toFixed(d);
  const pct=v=>num(v)==null?'—':`${num(v).toFixed(2)}%`;
  const signedPct=v=>num(v)==null?'—':`${num(v)>=0?'+':''}${num(v).toFixed(3)}%`;
  function readiness(n){return n>=200?'ROBUSTNESS TEST READY':n>=100?'VALIDATION READY':n>=30?'EARLY RESEARCH':'NOT READY';}
  function nextMilestone(n){if(n<30)return {target:30,label:'EARLY RESEARCH'};if(n<100)return {target:100,label:'VALIDATION READY'};if(n<200)return {target:200,label:'ROBUSTNESS TEST READY'};return {target:200,label:'ROBUSTNESS TEST READY'};}
  function evidenceVerdict(n,m){
    if(n<30)return 'INSUFFICIENT SAMPLE';
    const avg=num(m?.avg_return_pct), hit=num(m?.hit_rate_pct);
    if(avg==null||hit==null)return 'COLLECTING';
    if(avg>0&&hit>=50)return n>=100?'POSITIVE EDGE CANDIDATE':'EARLY POSITIVE READ';
    if(avg<0&&hit<50)return n>=100?'NEGATIVE EDGE EVIDENCE':'EARLY NEGATIVE READ';
    return 'MIXED EVIDENCE';
  }
  async function attrib(symbol,horizon){
    const q=new URLSearchParams({horizon:String(horizon),min_n:'2'});if(symbol)q.set('symbol',symbol);
    const r=await fetch(`/api/ai/attribution?${q.toString()}`,{cache:'no-store'});
    if(!r.ok)throw Error(`HTTP ${r.status}`);return r.json();
  }
  function renderSummary(p){
    const n=Number(p.matured||0), m=p.baseline||{}, next=nextMilestone(n), progress=Math.min(100,next.target?Math.round(n/next.target*100):100);
    const badge=$('edgeProofBadge'); if(badge){badge.textContent=readiness(n);badge.className=`pill ${n>=100?'buy':n>=30?'working':'neutral'}`;}
    const cards=[
      ['24h matured',n],['24h hit rate',pct(m.hit_rate_pct)],['24h expectancy',signedPct(m.avg_return_pct)],
      ['Drawdown proxy',pct(m.max_drawdown_proxy)],['Evidence verdict',evidenceVerdict(n,m)],['Next milestone',`${Math.min(n,next.target)}/${next.target} · ${next.label}`]
    ];
    if($('edgeProofMetrics'))$('edgeProofMetrics').innerHTML=cards.map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
    if($('edgeProofProgress'))$('edgeProofProgress').innerHTML=`<div class="muted small">Progress to ${next.label}: ${progress}%</div><div style="height:10px;border-radius:999px;background:rgba(148,163,184,.14);overflow:hidden;margin-top:8px"><div style="height:100%;width:${progress}%;background:currentColor"></div></div>`;
  }
  function renderHorizons(rows){
    const body=$('edgeHorizonBody');if(!body)return;
    body.innerHTML=rows.map(x=>{const m=x.baseline||{};return `<tr><td>${x.horizon_h}h</td><td>${x.matured||0}</td><td>${pct(m.hit_rate_pct)}</td><td>${signedPct(m.avg_return_pct)}</td><td>${pct(m.max_drawdown_proxy)}</td><td>${evidenceVerdict(Number(x.matured||0),m)}</td></tr>`}).join('');
  }
  function renderAssets(rows){
    const body=$('edgeAssetBody');if(!body)return;
    body.innerHTML=rows.map(x=>{const m=x.baseline||{},n=Number(x.matured||0);return `<tr><td>${x.symbol||'ALL'}</td><td>${n}</td><td>${pct(m.hit_rate_pct)}</td><td>${signedPct(m.avg_return_pct)}</td><td>${pct(m.max_drawdown_proxy)}</td><td>${readiness(n)}</td></tr>`}).join('');
  }
  function renderFactors(p){
    const body=$('edgeFactorBody');if(!body)return;
    const factors=[...(p.strongest_associations||[]).slice(0,5),...(p.weakest_associations||[]).slice(0,5)].filter((x,i,a)=>a.findIndex(y=>y.tag===x.tag)===i);
    body.innerHTML=factors.length?factors.map(x=>`<tr><td>${String(x.tag||'').replaceAll('_',' ')}</td><td>${x.n||0}</td><td>${pct(x.hit_rate_pct)}</td><td>${signedPct(x.avg_return_pct)}</td><td>${signedPct(x.delta_vs_baseline_avg_pct)}</td></tr>`).join(''):'<tr><td colspan="5">Not enough grouped evidence yet.</td></tr>';
  }
  async function refresh(){
    const badge=$('edgeProofBadge');if(badge){badge.textContent='CHECKING';badge.className='pill working';}
    try{
      const [global24,horizons,assets]=await Promise.all([
        attrib(null,24),Promise.all(HORIZONS.map(h=>attrib(null,h))),Promise.all(SYMBOLS.map(s=>attrib(s,24)))
      ]);
      renderSummary(global24);renderHorizons(horizons);renderAssets(assets);renderFactors(global24);
      if($('edgeProofNotes'))$('edgeProofNotes').textContent='AI-only frozen LONG/SHORT observations. Returns are directional and forward-looking; WAIT decisions are not counted as trades. No live execution.';
    }catch(e){
      if(badge){badge.textContent='UNAVAILABLE';badge.className='pill neutral';}
      if($('edgeProofNotes'))$('edgeProofNotes').textContent=`Edge proof data unavailable: ${e.message}`;
    }
  }
  $('edgeProofRefreshBtn')?.addEventListener('click',refresh);refresh();setInterval(refresh,60000);
})();