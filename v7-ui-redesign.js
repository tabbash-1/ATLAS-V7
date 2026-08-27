(() => {
  const $ = id => document.getElementById(id);
  const main = document.querySelector('main.main');
  const panelsHost = $('atlasWorkspacePanels');
  const nav = $('atlasWorkspaceNav');
  if (!main || !panelsHost || !nav) return;

  const WORKSPACES = {
    command: {label:'Command', eyebrow:'DAILY DECISION LAYER', title:'Command Center', sub:'The shortest path from market context to a research decision.'},
    market: {label:'Market', eyebrow:'MARKET MICROSTRUCTURE', title:'Market Intelligence', sub:'Structure, derivatives, liquidity, events and live engine metrics.'},
    trade: {label:'Trade', eyebrow:'TRADE CONSTRUCTION', title:'Trade & Risk', sub:'Playbook, entry geometry, position sizing and exit research.'},
    research: {label:'Research', eyebrow:'QUANT LAB', title:'Research Labs', sub:'Backtests, Smart Money archives, portfolio and factor validation.'},
    learning: {label:'Learning', eyebrow:'MODEL GOVERNANCE', title:'Learning & Validation', sub:'Memory, forward tests, drift, promotion gates and controlled shadow rollout.'},
    system: {label:'System', eyebrow:'INFRASTRUCTURE', title:'System & Data', sub:'Cloud collection, continuous forward lab, data quality and asset universe.'}
  };

  function titleOf(section){
    const strong = section.querySelector('.card-head strong');
    return (strong?.textContent || section.textContent || '').trim().toUpperCase();
  }

  function classify(section){
    const t=titleOf(section);
    if(section.classList.contains('lower-grid')) return 'command';
    if(t.includes('MASTER CONVICTION') || t.includes('OPPORTUNITY SCANNER') || t.includes('EARLY WARNING') || t.includes('CONFIRMED OPPORTUNITY ALERTS')) return 'command';

    if(t.includes('CONFLUENCE') || t.includes('FUTURES INTELLIGENCE') || t.includes('LIQUIDITY + LIQUIDATION') ||
       t.includes('LIVE ENGINE METRICS') || t.includes('EVENT RADAR')) return 'market';

    if(t.includes('TRADE MANAGEMENT') || t.includes('PORTFOLIO RISK') || t.includes('TRADER PLAYBOOKS') ||
       t.includes('EXIT RESEARCH')) return 'trade';

    if(t.includes('BACKTEST') || t.includes('MULTI-FACTOR LAB') || t.includes('SMART MONEY ARCHIVE') ||
       t.includes('SMART MONEY TIMELINE') || t.includes('SMART MONEY VALIDATION') ||
       t.includes('SPOT ALPHA') || t.includes('SPOT PORTFOLIO') || t.includes('WALK-FORWARD')) return 'research';

    if(t.includes('PATTERN MEMORY') || t.includes('POST-TRADE LEARNING') || t.includes('VALIDATION & PROMOTION') ||
       t.includes('CHAMPION VS CHALLENGER') || t.includes('ADAPTIVE') || t.includes('PROMOTION GATE') ||
       t.includes('CONTROLLED CANARY') || t.includes('STAGE EXPANSION') || t.includes('PERFORMANCE DASHBOARD')) return 'learning';

    if(t.includes('CLOUD FORWARD') || t.includes('CONTINUOUS FORWARD') || t.includes('DATA QUALITY & DRIFT') ||
       t.includes('MULTI‑ASSET UNIVERSE') || t.includes('MULTI-ASSET UNIVERSE')) return 'system';

    return 'research';
  }

  // Build workspace panels, then move the EXISTING nodes. IDs, listeners and engines stay intact.
  const fragments={};
  Object.entries(WORKSPACES).forEach(([key,meta])=>{
    const panel=document.createElement('section');
    panel.className='atlas-workspace-panel';
    panel.dataset.workspacePanel=key;
    panel.innerHTML=`<div class="workspace-heading">
      <div><div class="workspace-eyebrow">${meta.eyebrow}</div><h3>${meta.title}</h3><p>${meta.sub}</p></div>
      <span class="workspace-mode">RESEARCH ONLY</span>
    </div><div class="workspace-content"></div>`;
    panelsHost.appendChild(panel);
    fragments[key]=panel.querySelector('.workspace-content');
  });

  [...main.children].forEach(node=>{
    if(node.tagName!=='SECTION') return;
    if(node.classList.contains('chart-grid') || node.classList.contains('command-strip')) return;
    const target=classify(node);
    node.classList.add('atlas-module-card');
    fragments[target].appendChild(node);
  });

  // Cards that matter most in Command get an elevated visual hierarchy.
  ['masterBadge','opportunityBadge','anomalyBadge'].forEach(id=>{
    const el=$(id); if(el) el.closest('section,article')?.classList.add('priority-module');
  });

  function switchWorkspace(key, persist=true){
    if(!WORKSPACES[key]) key='command';
    nav.querySelectorAll('.workspace-tab').forEach(b=>{
      const on=b.dataset.workspace===key;
      b.classList.toggle('active',on);
      b.setAttribute('aria-selected',String(on));
    });
    panelsHost.querySelectorAll('.atlas-workspace-panel').forEach(p=>{
      p.classList.toggle('active',p.dataset.workspacePanel===key);
    });
    if(persist) localStorage.setItem('atlas.v7.workspace',key);
  }
  nav.addEventListener('click',e=>{
    const b=e.target.closest('.workspace-tab');
    if(!b) return;
    switchWorkspace(b.dataset.workspace);
  });
  const cloudTile=$('cmdCloudValue')?.closest('.command-tile');
  if(cloudTile){
    cloudTile.style.cursor='pointer';
    cloudTile.title='Open System & Data workspace';
    cloudTile.addEventListener('click',()=>switchWorkspace('system'));
  }
  switchWorkspace(localStorage.getItem('atlas.v7.workspace')||'command',false);

  // Mirror existing source-of-truth status into the always-visible Command Strip.
  const mirrors=[
    ['portfolioRiskBadge','cmdRiskValue'],
    ['playbookBadge','cmdPlaybookValue'],
    ['driftBadge','cmdDriftValue'],
    ['cloudForwardBadge','cmdCloudValue']
  ];
  const regimeSource=()=>document.querySelector('#regimeGrid b');

  function stateTone(text){
    const x=String(text||'').toUpperCase();
    if(/BUY|LONG|READY|OK|HEALTHY|STABLE|ENABLED|PASS|LEADING|PLAN_READY/.test(x)) return 'positive';
    if(/SELL|SHORT|BLOCK|FAIL|RISK|DEGRADED|ERROR|OFFLINE|ROLLBACK/.test(x)) return 'negative';
    if(/WATCH|WAIT|COLLECT|CHECK|WORKING|INCONCLUSIVE|ELEVATED/.test(x)) return 'warning';
    return 'neutral';
  }
  function paint(dest,text){
    if(!dest) return;
    const next=text||'—';
    if(dest.textContent!==next) dest.textContent=next;
    const tile=dest.closest('.command-tile');
    if(tile){
      tile.classList.remove('tone-positive','tone-negative','tone-warning','tone-neutral');
      tile.classList.add(`tone-${stateTone(text)}`);
    }
  }
  function updateCommandStrip(){
    mirrors.forEach(([srcId,dstId])=>{
      const src=$(srcId),dst=$(dstId);
      if(src&&dst) paint(dst,src.textContent.trim());
    });
    const rg=regimeSource();
    if(rg) paint($('cmdRegimeValue'),rg.textContent.trim());

    // Production Opportunity Runtime owns the decision and plan tiles.
    // Legacy browser research engines remain visible below but cannot overwrite them.
  }
  updateCommandStrip();

  let pending=false;
  const mo=new MutationObserver(()=>{
    if(pending) return;
    pending=true;
    requestAnimationFrame(()=>{pending=false;updateCommandStrip();});
  });
  mo.observe(document.body,{subtree:true,childList:true,characterData:true});

  // Add contextual labels to the current setup card without changing any engine IDs.
  const signalCard=document.querySelector('.signal-card');
  if(signalCard){
    signalCard.classList.add('current-setup-card');
    const score=signalCard.querySelector('.signal-score');
    if(score && !signalCard.querySelector('.setup-context-row')){
      const row=document.createElement('div');
      row.className='setup-context-row';
      row.innerHTML='<span>ATLAS RESEARCH SIGNAL</span><span>NO EXECUTION</span>';
      score.before(row);
    }
  }

  // Top-level shell marker enables CSS only after reorganization has succeeded.
  document.body.classList.add('atlas-v7-ready');
})();
