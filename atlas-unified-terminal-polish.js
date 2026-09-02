(()=>{
  const VERSION='ATLAS_UNIFIED_TERMINAL_POLISH_V2';
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
    'WAITING FOR TRIGGER':'Waiting for trigger',
    'READY ON TRIGGER':'Setup ready · trigger pending',
    'TRIGGER READY':'Setup ready · trigger pending',
    'READY':'Execution ready',
    'EXECUTION READY':'Execution ready',
    'BLOCKED':'Blocked',
    'WAIT':'Waiting',
    'WAITING':'Waiting'
  }[s]||s);
  const titleCase=s=>String(s||'').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());

  function setTextIfChanged(el,next){ if(el && el.textContent!==next) el.textContent=next; }
  function setHtmlIfChanged(el,next){ if(el && el.innerHTML!==next) el.innerHTML=next; }
  function polishScalar(id){
    const el=$(id); if(!el) return;
    const n=parseNumber(el.textContent.trim());
    if(n!==null) setTextIfChanged(el,smartPrice(n));
  }
  function polishTextNumbers(id){
    const el=$(id); if(!el) return;
    const next=el.textContent.replace(/-?\d{1,6}(?:\.\d{3,10})/g,m=>smartPrice(m));
    setTextIfChanged(el,next);
  }
  function polishTargets(){
    const el=$('auTargets'); if(!el) return;
    if(el.querySelector('span') && el.querySelector('small')) return;
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
    let state=prettyState((parts.slice(2).join(' · ')||'').toUpperCase());
    const action=($('auAction')?.textContent||'').trim().toUpperCase();
    if(action==='WAIT' && /READY ON TRIGGER|TRIGGER READY|SETUP READY/.test((parts.slice(2).join(' ')||'').toUpperCase())){
      state='Setup ready · trigger pending';
    }
    const next=[scenario,score?`${score}%`:null,state||null].filter(Boolean).join(' · ');
    setTextIfChanged(el,next);
  }
  function polishDecisionSemantics(){
    const action=($('auAction')?.textContent||'').trim().toUpperCase();
    const direction=($('auDir')?.textContent||'').trim().toUpperCase();
    const gate=$('auGate');
    const gateRaw=(gate?.textContent||'').trim();
    const gm=gateRaw.match(/(\d+)\s*\/\s*(\d+)/);
    const passed=gm?Number(gm[1]):null, total=gm?Number(gm[2]):null;
    const safetyComplete=passed!==null&&total!==null&&passed===total;
    if(gate && gm) setTextIfChanged(gate,`SAFETY ${passed}/${total}`);

    const trigger=($('auTrigger')?.textContent||'').trim();
    const thesis=$('auThesis');
    if(action==='WAIT' && ['LONG','SHORT'].includes(direction)){
      const next=safetyComplete
        ? `${direction} thesis is valid. Safety gates passed; execution stays WAIT until the required 1H trigger confirms.`
        : `${direction} thesis is developing. Execution stays WAIT until the remaining safety gates and the required 1H trigger align.`;
      setTextIfChanged(thesis,next);
    }

    const risk=$('auRisk');
    if(risk && action==='WAIT'){
      let html=risk.innerHTML;
      const execution=safetyComplete
        ? '<strong>Execution:</strong> WAIT · safety passed, trigger pending'
        : '<strong>Execution:</strong> WAIT · setup not fully confirmed';
      if(/<strong>Execution:<\/strong>.*?(?=<br>|$)/i.test(html)){
        html=html.replace(/<strong>Execution:<\/strong>.*?(?=<br>|$)/i,execution);
      }
      setHtmlIfChanged(risk,html);
    }

    const triggerBox=$('auTrigger');
    if(triggerBox && trigger && action==='WAIT' && safetyComplete){
      triggerBox.closest('.au-trigger')?.classList.add('au-trigger-pending');
    } else {
      triggerBox?.closest('.au-trigger')?.classList.remove('au-trigger-pending');
    }
  }
  function polish(){
    polishScalar('auEntry'); polishScalar('auStop'); polishScalar('auTp1');
    polishTargets(); polishScenario();
    polishTextNumbers('auTrigger'); polishTextNumbers('auInvalidation');
    polishDecisionSemantics();
  }

  const style=document.createElement('style');
  style.id='atlasUnifiedTerminalPolishStyle';
  style.textContent=`
    #atlasUnified .au-target-stack{display:flex;flex-direction:column;gap:3px;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.25}
    #atlasUnified .au-target-stack small{font-size:12px;font-weight:700;color:var(--au-muted,#94a3b8)}
    #atlasUnified .au-tile b{font-variant-numeric:tabular-nums}
    #atlasUnified .au-trigger-pending{border-color:#4b4530;background:rgba(45,35,14,.42)}
    #atlasUnified .au-trigger-pending .au-label{color:#f1c75b}
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
  const oldStyle=$('atlasUnifiedTerminalPolishStyle');
  if(oldStyle) oldStyle.replaceWith(style); else document.head.appendChild(style);

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
