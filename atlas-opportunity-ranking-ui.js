(() => {
  const VERSION='ATLAS_OPPORTUNITY_RANKING_UI_V1';
  const CORE=['BTCUSDT','ETHUSDT','SOLUSDT','BNBUSDT','XRPUSDT','DOGEUSDT','ZECUSDT'];
  const $=id=>document.getElementById(id);
  const human=v=>String(v||'').replace(/_/g,' ').replace(/\s+/g,' ').trim();
  const shell=$('atlasProductShell');
  if(!shell||$('atlasOpportunityRanking')) return;

  const style=document.createElement('style');
  style.textContent=`#atlasOpportunityRanking{margin-top:14px;border:1px solid #253047;border-radius:16px;background:#0d1320;padding:14px}.aor-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}.aor-title{font-size:16px;font-weight:900}.aor-note{font-size:11px;color:#8c9ab3}.aor-refresh{border:1px solid #385d52;background:#0a1714;color:#6fe5ad;border-radius:10px;padding:9px 12px;font-weight:800}.aor-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:12px}.aor-card{border:1px solid #28364d;background:#0b111b;border-radius:12px;padding:12px}.aor-rank{font-size:10px;letter-spacing:.09em;color:#9d7cff}.aor-symbol{font-weight:900;font-size:18px;margin:3px 0}.aor-score{font-size:13px}.aor-next{font-size:11px;color:#b6c2d5;margin-top:7px;line-height:1.45}.aor-tier{font-size:10px;color:#f4c95d}.aor-foot{margin-top:10px;color:#77869f;font-size:10px;line-height:1.5}@media(max-width:820px){.aor-grid{grid-template-columns:1fr}}`;
  document.head.appendChild(style);

  const box=document.createElement('section');
  box.id='atlasOpportunityRanking';
  box.dataset.version=VERSION;
  box.innerHTML=`<div class="aor-head"><div><div class="aps-label">Opportunity Readiness · Final Gate Diagnostic</div><div class="aor-title">Closest setups to TRADE READY</div><div id="aorStatus" class="aor-note">Press refresh to rank current Production decisions.</div></div><button id="aorRefresh" class="aor-refresh">Refresh Opportunities</button></div><div id="aorGrid" class="aor-grid"><div class="aor-card"><div class="aor-note">No ranking loaded yet.</div></div></div><div class="aor-foot">Readiness is a checklist score, not a win probability. It cannot change score, threshold, geometry, or FINAL_TRADE_GATE. Live execution remains off.</div>`;
  const anchor=shell.querySelector('.aps-ai')||shell.querySelector('.aps-summary-grid');
  if(anchor) shell.insertBefore(box,anchor); else shell.appendChild(box);

  function render(payload){
    const grid=$('aorGrid');
    if(!grid) return;
    if(!payload?.ok||payload?.decision_source_of_truth!=='FINAL_TRADE_GATE'||payload?.readiness_score_is_probability!==false||payload?.production_decision_changed!==false){
      grid.innerHTML='<div class="aor-card"><div class="aor-note">Ranking contract unavailable. Final Gate remains authoritative.</div></div>';
      return;
    }
    const rows=(payload.opportunities||[]).slice(0,3);
    grid.innerHTML=rows.map(r=>`<div class="aor-card"><div class="aor-rank">#${Number(r.rank)||'—'} · ${human(r.readiness_tier)}</div><div class="aor-symbol">${String(r.symbol||'—').replace('USDT','')}</div><div class="aor-score">Readiness <b>${Number(r.readiness_score)||0}/100</b> · Score ${r.score??'—'}/${r.signal_threshold??68}</div><div class="aor-tier">${r.trade_ready?'TRADE READY':'WAIT'}</div><div class="aor-next"><b>Next:</b> ${human(r.next_required_condition||'No missing condition')}<br><b>HTF:</b> ${human(r.htf_reason||r.htf_status||'—')}</div></div>`).join('')||'<div class="aor-card"><div class="aor-note">No opportunities returned.</div></div>';
  }

  async function refresh(){
    const btn=$('aorRefresh'),status=$('aorStatus');
    if(btn) btn.disabled=true;
    if(status) status.textContent='Analyzing 7 Production decisions…';
    try{
      const r=await fetch(`/api/opportunities/ranked?symbols=${encodeURIComponent(CORE.join(','))}&t=${Date.now()}`,{cache:'no-store'});
      const payload=await r.json();
      if(!r.ok) throw new Error(payload?.error||`HTTP ${r.status}`);
      render(payload);
      if(status) status.textContent=`Live · ${payload.opportunities?.filter(x=>x.trade_ready).length||0} TRADE READY · Final Gate source of truth`;
      window.ATLAS_OPPORTUNITY_RANKING=payload;
    }catch(err){
      if(status) status.textContent=`Ranking unavailable · ${err?.message||err}`;
      render(null);
    }finally{ if(btn) btn.disabled=false; }
  }

  $('aorRefresh')?.addEventListener('click',refresh);
  window.ATLAS_REFRESH_OPPORTUNITY_RANKING=refresh;
})();
