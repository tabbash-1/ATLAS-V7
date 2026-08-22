(() => {
  const $ = id => document.getElementById(id);
  const main = document.querySelector('main.main');
  if (!main || $('atlasProductShell')) return;

  const style = document.createElement('style');
  style.textContent = `
    body.atlas-product-focus .topbar{display:none!important}
    body.atlas-product-focus .command-strip{display:none!important}
    body.atlas-product-focus .signal-card{display:none!important}
    body.atlas-product-focus:not(.atlas-advanced-open) .atlas-workspace-nav,
    body.atlas-product-focus:not(.atlas-advanced-open) .atlas-workspace-panels{display:none!important}
    #atlasProductShell{margin:18px 0;padding:18px;border:1px solid #253047;border-radius:20px;background:linear-gradient(180deg,rgba(16,22,34,.98),rgba(10,14,22,.98));box-shadow:0 16px 38px rgba(0,0,0,.24)}
    .aps-top{display:flex;gap:14px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}.aps-eyebrow{font-size:11px;letter-spacing:.16em;color:#9d7cff;font-weight:800}.aps-title{font-size:clamp(25px,5vw,40px);margin:5px 0 2px}.aps-sub{color:#8c9ab3;font-size:13px}.aps-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.aps-control,.aps-secondary{border:1px solid #2a3851;background:#0d1320;color:#dce5f4;border-radius:11px;padding:10px 12px}.aps-control{min-width:92px}.aps-secondary{cursor:pointer}.aps-grid{display:grid;grid-template-columns:1.15fr repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}.aps-card{border:1px solid #253047;border-radius:15px;padding:13px;background:#0d1320;min-width:0}.aps-card.primary{background:radial-gradient(circle at top left,rgba(157,124,255,.17),#0d1320 60%)}.aps-label{font-size:10px;letter-spacing:.1em;color:#8c9ab3;text-transform:uppercase;margin-bottom:7px}.aps-value{font-size:20px;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.aps-value.long{color:#55d68b}.aps-value.short{color:#ff6b7a}.aps-value.wait{color:#f4c95d}.aps-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}.aps-analyze{border:1px solid #2d8f69;background:#0e2a20;color:#6fe5ad;border-radius:12px;padding:12px 18px;font-weight:800;cursor:pointer}.aps-analyze:disabled{opacity:.55;cursor:wait}.aps-note{color:#8c9ab3;font-size:12px}.aps-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px}.aps-summary{border-top:1px solid #253047;padding-top:12px;min-width:0}.aps-summary strong{display:block;font-size:11px;letter-spacing:.08em;color:#9d7cff;text-transform:uppercase;margin-bottom:6px}.aps-summary div{color:#c9d4e7;font-size:12px;line-height:1.5;white-space:normal}.aps-hidden-noncrypto{display:none!important}.aps-wait-geometry{opacity:.55}.aps-wait-geometry .aps-value{color:#8c9ab3}
    @media(max-width:820px){#atlasProductShell{margin-top:12px}.aps-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.aps-card.primary{grid-column:1/-1}.aps-summary-grid{grid-template-columns:1fr}.aps-top{display:block}.aps-controls{margin-top:12px}.aps-control,.aps-secondary{flex:1}}
  `;
  document.head.appendChild(style);

  const shell = document.createElement('section');
  shell.id = 'atlasProductShell';
  shell.innerHTML = `
    <div class="aps-top">
      <div><div class="aps-eyebrow">ATLAS · CRYPTO TRADE INTELLIGENCE</div><div id="apsAsset" class="aps-title">Current asset</div><div class="aps-sub">One decision. One trade plan. Full research context underneath.</div></div>
      <div class="aps-controls">
        <select id="apsTimeframe" class="aps-control" aria-label="Timeframe"></select>
        <button id="apsTheme" class="aps-secondary" type="button">Theme</button>
        <button id="apsAdvanced" class="aps-secondary" type="button">Advanced Research</button>
      </div>
    </div>
    <div class="aps-grid">
      <div class="aps-card primary"><div class="aps-label">Decision</div><div id="apsDecision" class="aps-value wait">WAIT</div></div>
      <div class="aps-card"><div class="aps-label">Confidence</div><div id="apsConfidence" class="aps-value">—</div></div>
      <div id="apsEntryCard" class="aps-card"><div class="aps-label">Entry</div><div id="apsEntry" class="aps-value">—</div></div>
      <div id="apsStopCard" class="aps-card"><div class="aps-label">Stop</div><div id="apsStop" class="aps-value">—</div></div>
      <div id="apsTargetCard" class="aps-card"><div class="aps-label">Target / R:R</div><div id="apsTarget" class="aps-value">—</div></div>
    </div>
    <div class="aps-actions"><button id="apsAnalyze" class="aps-analyze">▶ ANALYZE</button><div id="apsStatus" class="aps-note">Ready · existing engines preserved</div></div>
    <div class="aps-summary-grid">
      <div class="aps-summary"><strong>Why</strong><div id="apsWhy">Run analysis to see the strongest evidence.</div></div>
      <div class="aps-summary"><strong>Risks</strong><div id="apsRisks">Risk context will be summarized here.</div></div>
      <div class="aps-summary"><strong>What changes the decision</strong><div id="apsChanges">ATLAS will show the missing confirmation when the current decision is WAIT.</div></div>
    </div>`;

  const anchor = document.querySelector('.command-strip') || document.querySelector('.chart-grid') || main.firstElementChild;
  main.insertBefore(shell, anchor);
  document.body.classList.add('atlas-product-focus');

  function text(id, fallback='—'){ const el=$(id); return (el?.textContent || '').trim() || fallback; }
  function compact(v,max=170){ const s=String(v||'').replace(/\s+/g,' ').trim(); return s.length>max?s.slice(0,max-1)+'…':s; }
  function normalizeDecision(){
    const master = text('masterBadge','');
    const signal = text('signalState','WAIT');
    const raw = (master && !/WAITING|CHECKING|ARMING|READY/.test(master.toUpperCase())) ? master : signal;
    const u=String(raw).toUpperCase();
    if(/LONG|BUY/.test(u)) return 'LONG';
    if(/SHORT|SELL/.test(u)) return 'SHORT';
    return 'WAIT';
  }
  function metricPairs(containerId){
    const root=$(containerId); if(!root) return [];
    return [...root.querySelectorAll(':scope > div')].map(div=>{
      const k=div.querySelector('span')?.textContent?.trim();
      const v=div.querySelector('b')?.textContent?.trim();
      return k&&v?[k,v]:null;
    }).filter(Boolean);
  }
  function usefulPairs(pairs){ return pairs.filter(([,v])=>v && !/^(—|WAITING|READY|PENDING)$/i.test(v)); }

  function buildWhy(decision){
    const master=compact(text('masterNotes',''));
    if(master && !/Waiting for a live analysis/i.test(master)) return master;
    const pairs=usefulPairs(metricPairs('confluenceMetrics')).slice(0,4);
    if(pairs.length) return pairs.map(([k,v])=>`${k}: ${v}`).join(' · ');
    const regime=text('cmdRegimeValue','—');
    return decision==='WAIT' ? `No strict directional confirmation yet${regime!=='—'?` · regime ${regime}`:''}.` : `Directional confirmation is active${regime!=='—'?` · regime ${regime}`:''}.`;
  }
  function buildRisks(){
    const risk=text('cmdRiskValue','—'), drift=text('cmdDriftValue','—');
    const liq=compact(text('liquidityNotes',''));
    const bits=[];
    if(risk!=='—') bits.push(`Portfolio risk: ${risk}`);
    if(drift!=='—') bits.push(`Edge/drift: ${drift}`);
    if(liq && !/Waiting for liquidity context/i.test(liq)) bits.push(liq);
    return bits.length?bits.join(' · '):'Risk modules have not produced live context yet.';
  }
  function buildChanges(decision){
    const pairs=usefulPairs(metricPairs('confluenceMetrics'));
    const gate=pairs.find(([k])=>/gate reason/i.test(k));
    if(gate) return `Missing confirmation: ${gate[1]}`;
    const trend=text('trendState','Pending'), momentum=text('momentumState','Pending'), volume=text('volumeState','Pending'), structure=text('structureState','Pending');
    if(decision==='WAIT') return `Need stronger alignment across trend (${trend}), momentum (${momentum}), volume (${volume}) and structure (${structure}) before LONG/SHORT.`;
    return 'Decision changes if structure, momentum, liquidity or risk alignment invalidates the current setup.';
  }

  function syncTimeframe(){
    const src=$('intervalSelect'), dst=$('apsTimeframe');
    if(!src || !dst) return;
    if(!dst.options.length){
      [...src.options].forEach(o=>dst.add(new Option(o.textContent,o.value)));
      dst.addEventListener('change',()=>{
        src.value=dst.value;
        src.dispatchEvent(new Event('change',{bubbles:true}));
      });
    }
    if(dst.value!==src.value) dst.value=src.value;
  }

  function setGeometry(decision){
    const waiting=decision==='WAIT';
    ['apsEntryCard','apsStopCard','apsTargetCard'].forEach(id=>$(id)?.classList.toggle('aps-wait-geometry',waiting));
    if(waiting){
      $('apsEntry').textContent='—'; $('apsStop').textContent='—'; $('apsTarget').textContent='—';
      return;
    }
    $('apsEntry').textContent=text('entry','—');
    $('apsStop').textContent=text('stop','—');
    const tp=text('target','—'), rr=text('rr','—');
    $('apsTarget').textContent=rr==='—'?tp:`${tp} · ${rr}`;
  }

  function update(){
    syncTimeframe();
    const decision=normalizeDecision();
    const d=$('apsDecision'); d.textContent=decision; d.className='aps-value '+(decision==='LONG'?'long':decision==='SHORT'?'short':'wait');
    $('apsAsset').textContent=text('activeTitle','Current asset');
    $('apsConfidence').textContent=text('confidence','—');
    setGeometry(decision);
    $('apsWhy').textContent=buildWhy(decision);
    $('apsRisks').textContent=buildRisks();
    $('apsChanges').textContent=buildChanges(decision);
    const btn=$('analyzeBtn');
    $('apsAnalyze').disabled=!!btn?.disabled;
    $('apsStatus').textContent=btn?.disabled?'Analysis running… · existing engines preserved':decision==='WAIT'?'WAIT = no executable trade plan · existing engines preserved':'Research decision ready · existing engines preserved';
    $('apsAdvanced').textContent=document.body.classList.contains('atlas-advanced-open')?'Hide Advanced':'Advanced Research';
  }

  $('apsAnalyze').addEventListener('click',()=>$('analyzeBtn')?.click());
  $('apsTheme').addEventListener('click',()=>$('themeToggleBtn')?.click());
  $('apsAdvanced').addEventListener('click',()=>{
    document.body.classList.toggle('atlas-advanced-open');
    update();
    if(document.body.classList.contains('atlas-advanced-open')) $('atlasWorkspaceNav')?.scrollIntoView({behavior:'smooth',block:'start'});
  });

  function focusCryptoWatchlist(){
    document.querySelectorAll('#watchlist .watch-item').forEach(item=>{
      const symbol=(item.querySelector('.watch-symbol')?.textContent||'').toUpperCase();
      const tag=(item.querySelector('.class-tag')?.textContent||'').toUpperCase();
      item.classList.toggle('aps-hidden-noncrypto', tag && tag!=='CRYPTO' && !/USDT|BTC|ETH|SOL|XRP|BNB|DOGE|ZEC/.test(symbol));
    });
  }

  let pending=false;
  const mo=new MutationObserver(()=>{ if(pending)return; pending=true; requestAnimationFrame(()=>{pending=false;focusCryptoWatchlist();update();}); });
  mo.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['disabled','class','value']});
  focusCryptoWatchlist(); update();
  window.ATLAS_PRODUCT_SHELL={refresh:update};
})();