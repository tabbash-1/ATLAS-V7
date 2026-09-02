(()=>{
  const VERSION='ATLAS_UNIFIED_TERMINAL_POLISH_V1';
  if(window[VERSION]) return;
  window[VERSION]=true;

  const $=id=>document.getElementById(id);
  const parseNumber=value=>{
    if(value===null||value===undefined) return null;
    const n=Number(String(value).replace(/,/g,''));
    return Number.isFinite(n)?n:null;
  };
  const smartPrice=value=>{
    const n=parseNumber(value);
    if(n===null) return '—';
    const a=Math.abs(n);
    const digits=a>=100?2:a>=10?3:a>=1?4:a>=0.1?5:6;
    return n.toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:digits});
  };
  const prettyState=s=>({
    'WAIT TRIGGER':'Waiting for trigger',
    'READY ON TRIGGER':'Trigger ready',
    'READY':'Execution ready',
    'BLOCKED':'Blocked',
    'WAIT':'Waiting'
  }[s]||s);
  const titleCase=s=>String(s||'').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());

  function polishScalar(id){
    const el=$(id); if(!el) return;
    const n=parseNumber(el.textContent.trim());
    if(n!==null) el.textContent=smartPrice(n);
  }
  function polishTextNumbers(id){
    const el=$(id); if(!el) return;
    const text=el.textContent;
    el.textContent=text.replace(/-?\d{1,6}(?:\.\d{3,10})/g,m=>smartPrice(m));
  }
  function polishTargets(){
    const el=$('auTargets'); if(!el) return;
    const nums=(el.textContent.match(/-?[\d,.]+/g)||[]).map(parseNumber).filter(v=>v!==null);
    if(nums.length<2) return;
    el.classList.add('au-target-stack');
    const tile=el.closest('.au-tile'); if(tile) tile.classList.add('au-target-tile');
    el.replaceChildren();
    const a=document.createElement('span'); a.textContent=`TP2 ${smartPrice(nums[0])}`;
    const b=document.createElement('small'); b.textContent=`TP3 ${smartPrice(nums[1])}`;
    el.append(a,b);
  }
  function polishScenario(){
    const el=$('auScenario'); if(!el) return;
    const parts=el.textContent.split('·').map(x=>x.trim()).filter(Boolean);
    if(parts.length<2) return;
    const scenario=titleCase(parts[0]);
    const score=(parts[1].match(/\d+/)||[])[0];
    const state=prettyState((parts[2]||'').toUpperCase());
    el.textContent=[scenario,score?`${score}%`:null,state||null].filter(Boolean).join(' · ');
  }
  function polish(){
    polishScalar('auEntry'); polishScalar('auStop'); polishScalar('auTp1');
    polishTargets(); polishScenario();
    polishTextNumbers('auTrigger'); polishTextNumbers('auInvalidation');
  }

  const style=document.createElement('style');
  style.id='atlasUnifiedTerminalPolishStyle';
  style.textContent=`
    #atlasUnified .au-target-stack{display:flex;flex-direction:column;gap:3px;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.25}
    #atlasUnified .au-target-stack small{font-size:12px;font-weight:700;color:var(--au-muted,#94a3b8)}
    #atlasUnified .au-tile b{font-variant-numeric:tabular-nums}
    @media(max-width:820px){
      #atlasUnified .au-target-tile{grid-column:span 2}
      #atlasUnified .au-tile{min-width:0}
      #atlasUnified .au-tile b{font-size:14px}
      #atlasUnified .au-target-stack{font-size:14px}
    }
    @media(max-width:420px){
      #atlasUnified .au-plan{gap:8px}
      #atlasUnified .au-tile{padding:11px 10px}
      #atlasUnified .au-target-tile{grid-column:span 2}
    }
  `;
  document.head.appendChild(style);

  let scheduled=false;
  const schedule=()=>{
    if(scheduled) return; scheduled=true;
    requestAnimationFrame(()=>{scheduled=false;polish();});
  };
  const start=()=>{
    schedule();
    const root=$('atlasUnified')||document.body;
    new MutationObserver(schedule).observe(root,{subtree:true,childList:true,characterData:true});
  };
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();
