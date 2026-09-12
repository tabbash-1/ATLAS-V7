(() => {
  const $ = id => document.getElementById(id);
  const main = document.querySelector('main.main');
  const panelsHost = $('atlasWorkspacePanels');
  const nav = $('atlasWorkspaceNav');
  if (!main || !panelsHost || !nav) return;

  const WORKSPACES = {
    command: {label:'Command', eyebrow:'CANONICAL 4–12H ANALYSIS', title:'Analysis Center', sub:'The shortest path from market context to one clear LONG / SHORT / WAIT analysis.'},
    market: {label:'Market', eyebrow:'MARKET MICROSTRUCTURE', title:'Market Intelligence', sub:'Structure, derivatives, liquidity, events and live engine metrics.'},
    trade: {label:'Plan', eyebrow:'ANALYSIS GEOMETRY', title:'Plan & Risk', sub:'Playbook, Entry / Stop / Target geometry, invalidation and risk context. No order routing.'},
    research: {label:'Research', eyebrow:'QUANT LAB', title:'Research Labs', sub:'Backtests, archives, portfolio evidence and factor validation.'},
    learning: {label:'Evidence', eyebrow:'MODEL GOVERNANCE', title:'Evidence & Validation', sub:'Forward evaluation, attribution, drift, readiness gates and controlled research.'},
    system: {label:'System', eyebrow:'INFRASTRUCTURE', title:'System & Data', sub:'Cloud collection, data quality, freshness and asset universe.'}
  };

  function titleOf(section){const strong=section.querySelector('.card-head strong');return (strong?.textContent||section.textContent||'').trim().toUpperCase();}
  function classify(section){
    const t=titleOf(section);
    if(section.classList.contains('lower-grid')) return 'command';
    if(t.includes('MASTER CONVICTION')||t.includes('OPPORTUNITY SCANNER')||t.includes('EARLY WARNING')||t.includes('CONFIRMED OPPORTUNITY ALERTS')||t.includes('ANALYSIS ALERTS')) return 'command';
    if(t.includes('CONFLUENCE')||t.includes('FUTURES INTELLIGENCE')||t.includes('LIQUIDITY + LIQUIDATION')||t.includes('LIVE ENGINE METRICS')||t.includes('EVENT RADAR')) return 'market';
    if(t.includes('TRADE MANAGEMENT')||t.includes('PORTFOLIO RISK')||t.includes('TRADER PLAYBOOKS')||t.includes('EXIT RESEARCH')) return 'trade';
    if(t.includes('BACKTEST')||t.includes('MULTI-FACTOR LAB')||t.includes('SMART MONEY ARCHIVE')||t.includes('SMART MONEY TIMELINE')||t.includes('SMART MONEY VALIDATION')||t.includes('SPOT ALPHA')||t.includes('SPOT PORTFOLIO')||t.includes('WALK-FORWARD')) return 'research';
    if(t.includes('PATTERN MEMORY')||t.includes('POST-TRADE LEARNING')||t.includes('VALIDATION & PROMOTION')||t.includes('CHAMPION VS CHALLENGER')||t.includes('ADAPTIVE')||t.includes('PROMOTION GATE')||t.includes('CONTROLLED CANARY')||t.includes('STAGE EXPANSION')||t.includes('PERFORMANCE DASHBOARD')) return 'learning';
    if(t.includes('CLOUD FORWARD')||t.includes('CONTINUOUS FORWARD')||t.includes('DATA QUALITY & DRIFT')||t.includes('MULTI‑ASSET UNIVERSE')||t.includes('MULTI-ASSET UNIVERSE')) return 'system';
    return 'research';
  }

  const fragments={};
  Object.entries(WORKSPACES).forEach(([key,meta])=>{
    const panel=document.createElement('section');panel.className='atlas-workspace-panel';panel.dataset.workspacePanel=key;
    panel.innerHTML=`<div class="workspace-heading"><div><div class="workspace-eyebrow">${meta.eyebrow}</div><h3>${meta.title}</h3><p>${meta.sub}</p></div><span class="workspace-mode">ANALYSIS ONLY · 4–12H</span></div><div class="workspace-content"></div>`;
    panelsHost.appendChild(panel);fragments[key]=panel.querySelector('.workspace-content');
  });
  [...main.children].forEach(node=>{if(node.tagName!=='SECTION'||node.classList.contains('chart-grid')||node.classList.contains('command-strip'))return;const target=classify(node);node.classList.add('atlas-module-card');fragments[target].appendChild(node);});
  ['masterBadge','opportunityBadge','anomalyBadge'].forEach(id=>{const el=$(id);if(el)el.closest('section,article')?.classList.add('priority-module');});

  function switchWorkspace(key,persist=true){
    if(!WORKSPACES[key])key='command';
    nav.querySelectorAll('.workspace-tab').forEach(b=>{const on=b.dataset.workspace===key;b.classList.toggle('active',on);b.setAttribute('aria-selected',String(on));if(WORKSPACES[b.dataset.workspace]){const icon=b.querySelector('span')?.outerHTML||'';b.innerHTML=`${icon} ${WORKSPACES[b.dataset.workspace].label}`;}});
    panelsHost.querySelectorAll('.atlas-workspace-panel').forEach(p=>p.classList.toggle('active',p.dataset.workspacePanel===key));
    if(persist)localStorage.setItem('atlas.v7.workspace',key);
  }
  nav.addEventListener('click',e=>{const b=e.target.closest('.workspace-tab');if(b)switchWorkspace(b.dataset.workspace);});
  const cloudTile=$('cmdCloudValue')?.closest('.command-tile');if(cloudTile){cloudTile.style.cursor='pointer';cloudTile.title='Open System & Data workspace';cloudTile.addEventListener('click',()=>switchWorkspace('system'));}
  switchWorkspace(localStorage.getItem('atlas.v7.workspace')||'command',false);

  const mirrors=[['portfolioRiskBadge','cmdRiskValue'],['playbookBadge','cmdPlaybookValue'],['driftBadge','cmdDriftValue'],['cloudForwardBadge','cmdCloudValue']];
  const regimeSource=()=>document.querySelector('#regimeGrid b');
  function stateTone(text){const x=String(text||'').toUpperCase();if(/LONG|READY|OK|HEALTHY|STABLE|ENABLED|PASS|LEADING/.test(x))return'positive';if(/SHORT|BLOCK|FAIL|RISK|DEGRADED|ERROR|OFFLINE|ROLLBACK/.test(x))return'negative';if(/WATCH|WAIT|COLLECT|CHECK|WORKING|INCONCLUSIVE|ELEVATED/.test(x))return'warning';return'neutral';}
  function paint(dest,text){if(!dest)return;const next=text||'—';if(dest.textContent!==next)dest.textContent=next;const tile=dest.closest('.command-tile');if(tile){tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');tile.classList.add(`tone-${stateTone(text)}`);}}
  function updateCommandStrip(){mirrors.forEach(([srcId,dstId])=>{const src=$(srcId),dst=$(dstId);if(src&&dst)paint(dst,src.textContent.trim());});const rg=regimeSource();if(rg)paint($('cmdRegimeValue'),rg.textContent.trim());}
  updateCommandStrip();let pending=false;const mo=new MutationObserver(()=>{if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;updateCommandStrip();});});mo.observe(document.body,{subtree:true,childList:true,characterData:true});

  // Normalize legacy static labels without changing backend/raw audit fields.
  const commandLabels=document.querySelectorAll('.command-label');
  commandLabels.forEach(el=>{if(el.textContent.trim()==='PRODUCTION DECISION')el.textContent='CANONICAL ANALYSIS';if(el.textContent.trim()==='PRODUCTION PLAN')el.textContent='ANALYSIS PLAN';});
  const signalCard=document.querySelector('.signal-card');
  if(signalCard){
    signalCard.classList.add('current-setup-card');
    const sub=signalCard.querySelector('.card-head .muted.tiny');if(sub)sub.textContent='Canonical 4–12H analysis geometry · no execution';
    const desc=signalCard.querySelector('p.muted.small');if(desc)desc.textContent='ATLAS publishes one canonical LONG / SHORT / WAIT analysis. Entry, Stop and Target appear only when the 4–12H analysis is ready.';
    const score=signalCard.querySelector('.signal-score');if(score&&!signalCard.querySelector('.setup-context-row')){const row=document.createElement('div');row.className='setup-context-row';row.innerHTML='<span>CANONICAL ANALYST OUTPUT</span><span>NO ORDER ROUTING</span>';score.before(row);}
  }
  const sidebar=document.querySelector('.sidebar-footer span');if(sidebar)sidebar.textContent='Analysis only · live execution OFF';

  // Canonical Production Truth: one visible surface for official forward evidence.
  const truthStyle=document.createElement('style');
  truthStyle.textContent=`
    .atlas-truth-card{grid-column:1/-1;padding:0;overflow:hidden;border:1px solid rgba(110,130,255,.22);background:linear-gradient(145deg,rgba(20,26,45,.98),rgba(12,16,30,.98))}
    .atlas-truth-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:20px 22px;border-bottom:1px solid rgba(255,255,255,.08)}
    .atlas-truth-kicker{font-size:11px;letter-spacing:.16em;font-weight:800;color:#93a4ff}.atlas-truth-head h3{margin:4px 0 4px;font-size:22px}.atlas-truth-head p{margin:0;color:var(--muted,#9aa4b8);font-size:13px}
    .atlas-truth-badges{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.truth-badge{font-size:10px;font-weight:800;letter-spacing:.08em;border-radius:999px;padding:6px 9px;border:1px solid rgba(255,255,255,.12);white-space:nowrap}.truth-badge.good{color:#7ff0c2;background:rgba(44,196,144,.1)}.truth-badge.warn{color:#ffd27c;background:rgba(255,183,77,.1)}.truth-badge.info{color:#a9b7ff;background:rgba(99,116,255,.12)}
    .atlas-truth-grid{display:grid;grid-template-columns:repeat(6,minmax(105px,1fr));gap:1px;background:rgba(255,255,255,.06)}.truth-stat{background:rgba(12,16,30,.96);padding:15px 16px;min-height:78px}.truth-stat span{display:block;color:var(--muted,#9aa4b8);font-size:10px;text-transform:uppercase;letter-spacing:.08em}.truth-stat b{display:block;margin-top:5px;font-size:20px}.truth-stat small{color:var(--muted,#9aa4b8);font-size:10px}
    .atlas-truth-split{display:grid;grid-template-columns:1.15fr .85fr;gap:0;border-top:1px solid rgba(255,255,255,.06)}.truth-pane{padding:18px 20px}.truth-pane+.truth-pane{border-left:1px solid rgba(255,255,255,.07)}.truth-pane h4{margin:0 0 12px;font-size:12px;letter-spacing:.1em}.truth-lines{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 18px}.truth-line{display:flex;justify-content:space-between;gap:12px;border-bottom:1px dashed rgba(255,255,255,.08);padding:7px 0;font-size:12px}.truth-line span{color:var(--muted,#9aa4b8)}.truth-line b{text-align:right}.truth-note{margin-top:12px;border:1px solid rgba(255,183,77,.22);background:rgba(255,183,77,.06);padding:10px 12px;border-radius:9px;font-size:11px;color:#d8c59b}.truth-source{padding:10px 20px;border-top:1px solid rgba(255,255,255,.06);font-size:10px;color:var(--muted,#9aa4b8);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
    .truth-table-wrap{overflow:auto;margin-top:10px}.truth-table{width:100%;border-collapse:collapse;font-size:11px}.truth-table th,.truth-table td{padding:8px 7px;border-bottom:1px solid rgba(255,255,255,.07);text-align:left;white-space:nowrap}.truth-table th{color:var(--muted,#9aa4b8);font-weight:600}.truth-result-win{color:#7ff0c2}.truth-result-loss{color:#ff8b99}.truth-result-expired{color:#ffd27c}
    @media(max-width:1100px){.atlas-truth-grid{grid-template-columns:repeat(3,1fr)}.atlas-truth-split{grid-template-columns:1fr}.truth-pane+.truth-pane{border-left:0;border-top:1px solid rgba(255,255,255,.07)}}
    @media(max-width:650px){.atlas-truth-head{flex-direction:column}.atlas-truth-badges{justify-content:flex-start}.atlas-truth-grid{grid-template-columns:repeat(2,1fr)}.truth-lines{grid-template-columns:1fr}.truth-stat b{font-size:17px}}
  `;
  document.head.appendChild(truthStyle);

  const truthCard=document.createElement('section');
  truthCard.className='card atlas-truth-card priority-module';
  truthCard.id='atlasProductionTruth';
  truthCard.innerHTML=`
    <div class="atlas-truth-head">
      <div><div class="atlas-truth-kicker">SOURCE OF TRUTH · FINAL TRADE GATE</div><h3>ATLAS Production Truth</h3><p>Official canonical forward evidence only. Research, shadow and historical cohorts stay separated.</p></div>
      <div class="atlas-truth-badges"><span class="truth-badge info">CORE 4–12H</span><span class="truth-badge warn" id="truthSampleBadge">LOADING</span><span class="truth-badge good">PAPER ONLY</span><span class="truth-badge info">LIVE EXECUTION OFF</span></div>
    </div>
    <div class="atlas-truth-grid" id="truthStats"><div class="truth-stat"><span>Status</span><b>Loading…</b><small>canonical data</small></div></div>
    <div class="atlas-truth-split">
      <div class="truth-pane"><h4>CANONICAL PORTFOLIO</h4><div class="truth-lines" id="truthPortfolioLines"></div><div class="truth-note" id="truthCostNote">Loading cost policy…</div></div>
      <div class="truth-pane"><h4>FORWARD EVIDENCE & COHORT CONTROL</h4><div class="truth-lines" id="truthForwardLines"></div><div class="truth-note">Production / Canonical Forward / Shadow / Historical are intentionally not merged. Historical and shadow evidence cannot override Production KPIs.</div></div>
    </div>
    <div class="truth-pane"><h4>OFFICIAL CANONICAL TRADES</h4><div class="truth-table-wrap"><table class="truth-table"><thead><tr><th>Captured</th><th>Asset</th><th>Side</th><th>Score</th><th>Entry</th><th>SL</th><th>TP2</th><th>R:R</th><th>Outcome</th><th>R</th><th>P&L</th></tr></thead><tbody id="truthTradeRows"><tr><td colspan="11">Loading canonical trade ledger…</td></tr></tbody></table></div></div>
    <div class="truth-source"><span id="truthFreshness">Generated: —</span><span>Sources: status/canonical-outcomes-latest.json · status/paper-portfolio-10k-latest.json</span></div>`;
  fragments.command.prepend(truthCard);

  const esc=v=>String(v??'—').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:d,minimumFractionDigits:d}):'—';
  const signed=(v,d=2)=>Number.isFinite(Number(v))?`${Number(v)>0?'+':''}${num(v,d)}`:'—';
  const money=v=>Number.isFinite(Number(v))?`${Number(v)<0?'-':''}$${Math.abs(Number(v)).toLocaleString(undefined,{maximumFractionDigits:2,minimumFractionDigits:2})}`:'—';
  const pct=v=>Number.isFinite(Number(v))?`${num(v,2)}%`:'—';
  const when=v=>{if(!v)return'—';const d=new Date(v);return Number.isNaN(d.getTime())?String(v):d.toLocaleString();};
  const price=v=>{const n=Number(v);if(!Number.isFinite(n))return'—';return n>=100?num(n,2):n>=1?num(n,4):n.toFixed(6);};
  async function fetchTruth(url){const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`${r.status} ${url}`);return r.json();}
  function truthStat(label,value,sub=''){return `<div class="truth-stat"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(sub)}</small></div>`;}
  function truthLine(label,value){return `<div class="truth-line"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;}
  function settlementTone(s){const x=String(s||'').toUpperCase();if(x.includes('WIN')||x.includes('TP'))return'truth-result-win';if(x.includes('LOSS')||x.includes('STOP'))return'truth-result-loss';return'truth-result-expired';}

  async function renderProductionTruth(){
    try{
      const [outcomes,paper]=await Promise.all([fetchTruth('status/canonical-outcomes-latest.json'),fetchTruth('status/paper-portfolio-10k-latest.json')]);
      const p=paper.portfolio||outcomes.path_summary||{};
      const summary=outcomes.summary||{};
      const rows=(outcomes.signals&&Array.isArray(outcomes.signals.rows)?outcomes.signals.rows:paper.trades)||[];
      const entries=Number(p.entries??p.closed??rows.length)||0;
      const sampleState=entries<10?'EARLY · INSUFFICIENT SAMPLE':entries<30?'BUILDING SAMPLE':'MATURED SAMPLE';
      const sampleBadge=$('truthSampleBadge');if(sampleBadge){sampleBadge.textContent=sampleState;sampleBadge.className=`truth-badge ${entries<10?'warn':'good'}`;}
      $('truthStats').innerHTML=[
        truthStat('Official trades',entries,`${p.wins??'—'}W · ${p.losses??'—'}L`),
        truthStat('Win rate',pct(p.win_rate_pct),'canonical closed'),
        truthStat('Net R',signed(p.net_r,4),'gross paper'),
        truthStat('Profit factor',num(p.profit_factor,4),'gross paper'),
        truthStat('Max drawdown',pct(p.max_drawdown_pct),'equity curve'),
        truthStat('Return',pct(p.return_pct??((Number(p.equity_usd||0)/Number(p.starting_equity_usd||10000)-1)*100)),money(p.net_pnl_usd))
      ].join('');
      $('truthPortfolioLines').innerHTML=[
        truthLine('Starting equity',money(p.starting_equity_usd)),truthLine('Current equity',money(p.equity_usd)),
        truthLine('Average R',signed(p.avg_r,4)),truthLine('Open / unresolved',p.open_or_unresolved??0),
        truthLine('LONG cohort',`${p.long?.closed??0} closed · ${pct(p.long?.win_rate_pct)} · ${money(p.long?.pnl_usd)}`),
        truthLine('SHORT cohort',`${p.short?.closed??0} closed · ${pct(p.short?.win_rate_pct)} · ${money(p.short?.pnl_usd)}`),
        truthLine('Decision authority',outcomes.official_trade_authority||outcomes.decision_source_of_truth||paper.decision_source_of_truth||'—'),
        truthLine('Product horizon',outcomes.product_horizon||paper.product_horizon||'4-12H')
      ].join('');
      $('truthForwardLines').innerHTML=[
        truthLine('Forward TRADE_READY',summary.forward_trade_ready_count??'—'),
        truthLine('Forward directional WAIT',summary.forward_wait_directional_count??'—'),
        truthLine('Frozen geometry coverage',outcomes.geometry_status?.coverage_pct!=null?pct(outcomes.geometry_status.coverage_pct):'—'),
        truthLine('Canonical rows',outcomes.geometry_status?.canonical_trade_rows??rows.length),
        truthLine('Threshold',paper.production_threshold_unchanged??outcomes.safety?.production_threshold_unchanged??'—'),
        truthLine('Legacy backfill',outcomes.legacy_backfill_allowed===false?'DISABLED':'—'),
        truthLine('Can override Production',outcomes.safety?.can_override_production===false?'NO':'—'),
        truthLine('Execution',paper.live_execution===false?'OFF':'—')
      ].join('');
      $('truthCostNote').textContent=paper.cost_note||'Gross paper performance; live trading costs are not included.';
      $('truthFreshness').textContent=`Generated: ${when(paper.generated_at||outcomes.generated_at)} · Observed through: ${when(paper.observed_through_at||outcomes.settlement_status?.observed_through_at)}`;
      $('truthTradeRows').innerHTML=rows.length?rows.map(r=>{const g=r.geometry||{};const s=r.settlement||{};return `<tr><td>${esc(when(r.captured_at))}</td><td><b>${esc(r.symbol)}</b></td><td>${esc(r.direction)}</td><td>${esc(num(r.score,0))}</td><td>${esc(price(g.entry))}</td><td>${esc(price(g.stop_loss))}</td><td>${esc(price(g.tp2))}</td><td>${esc(num(g.rr_tp2,2))}</td><td class="${settlementTone(s.status)}">${esc(s.status||'OPEN')}</td><td>${esc(signed(s.r_multiple,4))}</td><td>${esc(money(r.pnl_usd))}</td></tr>`;}).join(''):'<tr><td colspan="11">No canonical trades recorded.</td></tr>';
    }catch(err){
      $('truthStats').innerHTML=truthStat('Data status','UNAVAILABLE','canonical JSON could not be loaded');
      $('truthPortfolioLines').innerHTML=truthLine('Error',err.message||String(err));
      $('truthForwardLines').innerHTML=truthLine('Safety','No fallback KPIs displayed');
      $('truthTradeRows').innerHTML='<tr><td colspan="11">Canonical trade ledger unavailable. ATLAS will not substitute historical/shadow data.</td></tr>';
      const badge=$('truthSampleBadge');if(badge){badge.textContent='DATA CHECK';badge.className='truth-badge warn';}
    }
  }
  renderProductionTruth();
  window.setInterval(renderProductionTruth,60000);

  document.body.classList.add('atlas-v7-ready');
})();
