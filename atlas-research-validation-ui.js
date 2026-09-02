(()=>{
const VERSION='ATLAS_RESEARCH_VALIDATION_UI_V1';
const ENDPOINTS={
  offline:'/api/research/offline-forward-evaluation',
  guardrails:'/api/research/forward-robustness-guardrails',
  prospective:'/api/research/prospective-direction-guardrail'
};
const $=id=>document.getElementById(id);
const finite=v=>v!==null&&v!==undefined&&v!==''&&Number.isFinite(Number(v));
const pct=v=>finite(v)?`${Number(v).toFixed(2)}%`:'—';
const num=v=>finite(v)?String(Number(v)):'—';
const human=v=>String(v||'').replaceAll('_',' ').replace(/\s+/g,' ').trim();
function style(){
  if($('atlasResearchValidationStyle'))return;
  const s=document.createElement('style');s.id='atlasResearchValidationStyle';s.textContent=`
#atlasResearchValidation{margin-top:12px;border:1px solid #202e44;border-radius:20px;background:#0a1019;padding:17px;color:#edf3ff}
.arv-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.arv-head strong{font-size:13px}.arv-lock{font-size:9px;color:#8fe0b5;border:1px solid #315947;border-radius:99px;padding:5px 8px;white-space:nowrap}.arv-sub{margin-top:5px;color:#73849b;font-size:10px;line-height:1.45}.arv-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:13px}.arv-card{border:1px solid #233148;border-radius:14px;padding:13px;background:#0c1421;min-width:0}.arv-card span{display:block;color:#8392a8;font-size:9px;text-transform:uppercase;letter-spacing:.08em}.arv-card b{display:block;margin-top:6px;font-size:13px}.arv-card small{display:block;margin-top:6px;color:#8f9db1;font-size:10px;line-height:1.5}.arv-progress{height:5px;background:#182337;border-radius:99px;overflow:hidden;margin-top:8px}.arv-progress i{display:block;height:100%;background:linear-gradient(90deg,#785cff,#63d7a3);border-radius:99px}.arv-flags{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}.arv-flag{font-size:9px;border:1px solid #4c3a48;color:#dfa0aa;background:#1d1118;border-radius:99px;padding:5px 8px}.arv-flag.info{border-color:#304f62;color:#89c9e6;background:#0c1821}.arv-foot{margin-top:10px;color:#64738a;font-size:9px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
@media(max-width:820px){.arv-grid{grid-template-columns:1fr}.arv-head{align-items:flex-start}.arv-lock{white-space:normal;text-align:right}}
`;document.head.appendChild(s);
}
function ensure(){
  style();let el=$('atlasResearchValidation');if(el)return el;
  const host=$('atlasUnified');if(!host)return null;
  el=document.createElement('section');el.id='atlasResearchValidation';el.innerHTML=`
    <div class="arv-head"><div><strong>Research Validation</strong><div class="arv-sub">Retrospective diagnostics + preregistered forward proof. This layer cannot change the visible trade decision.</div></div><span class="arv-lock">NO PRODUCTION AUTHORITY</span></div>
    <div class="arv-grid">
      <div class="arv-card"><span>Retrospective 4H</span><b id="arvRetro">Loading…</b><small id="arvRetroSub">Committed forward evidence</small></div>
      <div class="arv-card"><span>Prospective SHORT / TREND DOWN</span><b id="arvShort">Loading…</b><div class="arv-progress"><i id="arvShortBar" style="width:0%"></i></div><small id="arvShortSub">Preregistered 4H cohort</small></div>
      <div class="arv-card"><span>Prospective LONG / TREND UP</span><b id="arvLong">Loading…</b><div class="arv-progress"><i id="arvLongBar" style="width:0%"></i></div><small id="arvLongSub">Preregistered caution cohort</small></div>
    </div>
    <div id="arvFlags" class="arv-flags"></div>
    <div class="arv-foot"><span id="arvState">Research state —</span><span id="arvAge">Report age —</span></div>`;
  const foot=host.querySelector('.au-foot');if(foot)host.insertBefore(el,foot);else host.appendChild(el);
  return el;
}
async function get(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}
function progress(m){const n=Number(m?.matured||0),t=Math.max(1,Number(m?.target||30));return Math.max(0,Math.min(100,100*n/t));}
function render(data){
  if(!ensure())return;
  const off=data.offline||{},g=data.guardrails||{},p=data.prospective||{};
  const short4=off?.qualified_by_direction?.SHORT?.['4']||{};
  $('arvRetro').textContent=finite(short4.mean_pct)?`SHORT 4H ${pct(short4.mean_pct)} · ${pct(short4.positive_rate_pct)} positive`:'Insufficient retrospective data';
  $('arvRetroSub').textContent=`n=${num(short4.n)} · diagnostic only · not trade P/L`;
  const sp=p?.sample_progress?.SHORT_TREND_DOWN_4H||{},lp=p?.sample_progress?.LONG_TREND_UP_CAUTION_4H||{};
  $('arvShort').textContent=`${num(sp.matured)} / ${num(sp.target||30)} matured`;$('arvShortBar').style.width=`${progress(sp)}%`;
  $('arvShortSub').textContent=p?.claims?.short_4h_edge_supported?'Forward threshold met — still research only':`Remaining ${num(sp.remaining)} · fixed 4H protocol`;
  $('arvLong').textContent=`${num(lp.matured)} / ${num(lp.target||30)} matured`;$('arvLongBar').style.width=`${progress(lp)}%`;
  $('arvLongSub').textContent=p?.claims?.long_trend_up_caution_supported?'Forward caution supported — still research only':`Remaining ${num(lp.remaining)} · fixed 4H protocol`;
  const flags=$('arvFlags');flags.innerHTML='';for(const x of (g.flags||[])){const e=document.createElement('span');e.className='arv-flag '+(x.severity==='INFO'?'info':'');e.textContent=human(x.id);flags.appendChild(e)}
  $('arvState').textContent=p?.claims?.claims_ready?'Prospective claims ready for review':'Prospective proof collecting · no promotion allowed';
  const ages=[off.report_age_hours,g.report_age_hours,p.report_age_hours].filter(finite).map(Number);$('arvAge').textContent=ages.length?`Newest API age ≤ ${Math.max(...ages).toFixed(2)}h`:'Report age unavailable';
  window.ATLAS_RESEARCH_VALIDATION={version:VERSION,loaded:true,claims_ready:!!p?.claims?.claims_ready,can_override_production:false,can_change_threshold:false};
}
async function refresh(){
  ensure();try{const [offline,guardrails,prospective]=await Promise.all([get(ENDPOINTS.offline),get(ENDPOINTS.guardrails),get(ENDPOINTS.prospective)]);render({offline,guardrails,prospective});}
  catch(e){if(ensure()){$('arvState').textContent=`Research feed unavailable · ${e.message}`;$('arvAge').textContent='Production decision unaffected';}window.ATLAS_RESEARCH_VALIDATION={version:VERSION,loaded:false,error:String(e),can_override_production:false,can_change_threshold:false};}
}
function boot(){if(!ensure()){setTimeout(boot,300);return}refresh();const b=$('auAnalyze');if(b&&!b.dataset.researchHook){b.dataset.researchHook='1';b.addEventListener('click',()=>setTimeout(refresh,1800));}}
window.ATLAS_RESEARCH_VALIDATION_UI={version:VERSION,refresh};
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot):boot();
})();
