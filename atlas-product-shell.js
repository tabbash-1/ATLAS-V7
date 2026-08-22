(() => {
  const $ = id => document.getElementById(id);
  const main = document.querySelector('main.main');
  if (!main || $('atlasProductShell')) return;

  const style = document.createElement('style');
  style.textContent = `
    #atlasProductShell{margin:0 0 18px;padding:18px;border:1px solid #253047;border-radius:20px;background:linear-gradient(180deg,rgba(16,22,34,.96),rgba(10,14,22,.96));box-shadow:0 16px 38px rgba(0,0,0,.24)}
    .aps-top{display:flex;gap:14px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}.aps-eyebrow{font-size:11px;letter-spacing:.16em;color:#9d7cff;font-weight:800}.aps-title{font-size:clamp(24px,4vw,38px);margin:5px 0 2px}.aps-sub{color:#8c9ab3;font-size:13px}.aps-grid{display:grid;grid-template-columns:1.1fr repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}.aps-card{border:1px solid #253047;border-radius:15px;padding:13px;background:#0d1320;min-width:0}.aps-card.primary{background:radial-gradient(circle at top left,rgba(157,124,255,.17),#0d1320 60%)}.aps-label{font-size:10px;letter-spacing:.1em;color:#8c9ab3;text-transform:uppercase;margin-bottom:7px}.aps-value{font-size:20px;font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.aps-value.long{color:#55d68b}.aps-value.short{color:#ff6b7a}.aps-value.wait{color:#f4c95d}.aps-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}.aps-analyze{border:1px solid #2d8f69;background:#0e2a20;color:#6fe5ad;border-radius:12px;padding:12px 18px;font-weight:800;cursor:pointer}.aps-note{display:flex;align-items:center;color:#8c9ab3;font-size:12px}.aps-reason{margin-top:14px;padding-top:13px;border-top:1px solid #253047;color:#c9d4e7;font-size:13px;line-height:1.55}.aps-hidden-noncrypto{display:none!important}
    @media(max-width:820px){.aps-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.aps-card.primary{grid-column:1/-1}}`;
  document.head.appendChild(style);

  const shell = document.createElement('section');
  shell.id = 'atlasProductShell';
  shell.innerHTML = `
    <div class="aps-top"><div><div class="aps-eyebrow">ATLAS · CRYPTO TRADE INTELLIGENCE</div><div id="apsAsset" class="aps-title">Current asset</div><div class="aps-sub">One decision surface over the existing ATLAS engines · research only</div></div></div>
    <div class="aps-grid">
      <div class="aps-card primary"><div class="aps-label">Decision</div><div id="apsDecision" class="aps-value wait">WAIT</div></div>
      <div class="aps-card"><div class="aps-label">Confidence</div><div id="apsConfidence" class="aps-value">—</div></div>
      <div class="aps-card"><div class="aps-label">Entry</div><div id="apsEntry" class="aps-value">—</div></div>
      <div class="aps-card"><div class="aps-label">Stop</div><div id="apsStop" class="aps-value">—</div></div>
      <div class="aps-card"><div class="aps-label">Target / R:R</div><div id="apsTarget" class="aps-value">—</div></div>
    </div>
    <div class="aps-actions"><button id="apsAnalyze" class="aps-analyze">▶ ANALYZE</button><div id="apsStatus" class="aps-note">Ready · uses the existing Analyze Live pipeline</div></div>
    <div id="apsReason" class="aps-reason">Run analysis to produce a consolidated LONG / SHORT / WAIT view. Existing research modules remain untouched below.</div>`;

  const anchor = document.querySelector('.command-strip') || document.querySelector('.chart-grid') || main.firstElementChild;
  main.insertBefore(shell, anchor);

  function text(id, fallback='—'){ const el=$(id); return (el?.textContent || '').trim() || fallback; }
  function normalizeDecision(){
    const master = text('masterBadge','');
    const signal = text('signalState','WAIT');
    const raw = (master && !/WAITING|CHECKING|ARMING|READY/.test(master.toUpperCase())) ? master : signal;
    const u=String(raw).toUpperCase();
    if(/LONG|BUY/.test(u)) return 'LONG';
    if(/SHORT|SELL/.test(u)) return 'SHORT';
    return 'WAIT';
  }
  function update(){
    const decision=normalizeDecision();
    const d=$('apsDecision'); d.textContent=decision; d.className='aps-value '+(decision==='LONG'?'long':decision==='SHORT'?'short':'wait');
    $('apsAsset').textContent=text('activeTitle','Current asset');
    $('apsConfidence').textContent=text('confidence','—');
    $('apsEntry').textContent=text('entry','—');
    $('apsStop').textContent=text('stop','—');
    const tp=text('target','—'), rr=text('rr','—'); $('apsTarget').textContent = rr==='—' ? tp : `${tp} · ${rr}`;
    const regime = text('cmdRegimeValue', text('regimeGrid','—'));
    const master = text('cmdMasterSub','No live analysis');
    const provider = text('providerLabel','');
    $('apsReason').textContent = `${master}${regime && regime!=='—' ? ` · Regime ${regime}` : ''}${provider ? ` · ${provider}` : ''}`;
    const btn=$('analyzeBtn');
    $('apsAnalyze').disabled=!!btn?.disabled;
    $('apsStatus').textContent=btn?.disabled?'Analysis running…':'Ready · existing engines preserved';
  }

  $('apsAnalyze').addEventListener('click',()=>$('analyzeBtn')?.click());

  // Visual crypto focus only. Never mutates ATLAS state or removes assets.
  function focusCryptoWatchlist(){
    document.querySelectorAll('#watchlist .watch-item').forEach(item=>{
      const symbol=(item.querySelector('.watch-symbol')?.textContent||'').toUpperCase();
      const tag=(item.querySelector('.class-tag')?.textContent||'').toUpperCase();
      item.classList.toggle('aps-hidden-noncrypto', tag && tag!=='CRYPTO' && !/USDT|BTC|ETH|SOL|XRP|BNB|DOGE|ZEC/.test(symbol));
    });
  }

  let pending=false;
  const mo=new MutationObserver(()=>{ if(pending)return; pending=true; requestAnimationFrame(()=>{pending=false;focusCryptoWatchlist();update();}); });
  mo.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['disabled','class']});
  focusCryptoWatchlist(); update();
  window.ATLAS_PRODUCT_SHELL={refresh:update};
})();