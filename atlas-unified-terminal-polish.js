(()=>{
  const VERSION='ATLAS_UNIFIED_TERMINAL_POLISH_V4_WAIT_CAUSE';
  if(window[VERSION]) return;
  window[VERSION]=true;
  const $=id=>document.getElementById(id);
  const parseNumber=value=>{if(value===null||value===undefined)return null;const n=Number(String(value).replace(/,/g,''));return Number.isFinite(n)?n:null};
  const smartPrice=value=>{const n=parseNumber(value);if(n===null)return'—';const a=Math.abs(n),digits=a>=100?2:a>=10?3:a>=1?4:a>=0.1?5:6;return n.toLocaleString(undefined,{minimumFractionDigits:0,maximumFractionDigits:digits})};
  const setText=(el,next)=>{if(el&&el.textContent!==next)el.textContent=next};
  function polishScalar(id){const el=$(id);if(!el)return;const n=parseNumber(el.textContent.trim());if(n!==null)setText(el,smartPrice(n))}
  function polishTextNumbers(id){const el=$(id);if(!el)return;setText(el,el.textContent.replace(/-?\d{1,6}(?:\.\d{3,10})/g,m=>smartPrice(m)))}
  function polishTargets(){const el=$('auTargets');if(!el||el.querySelector('span'))return;const nums=(el.textContent.match(/-?[\d,.]+/g)||[]).map(parseNumber).filter(v=>v!==null);if(nums.length<2)return;el.classList.add('au-target-stack');el.closest('.au-tile')?.classList.add('au-target-tile');el.replaceChildren();const a=document.createElement('span'),b=document.createElement('small');a.textContent=`TP2 ${smartPrice(nums[0])}`;b.textContent=`TP3 ${smartPrice(nums[1])}`;el.append(a,b)}
  function waitSemantics(){
    const action=($('auAction')?.textContent||'').trim().toUpperCase();if(action!=='WAIT')return;
    const direction=($('auDir')?.textContent||'').trim().toUpperCase(),risk=$('auRisk'),raw=(risk?.textContent||'').toUpperCase();
    const unqualified=/RAW QUALIFICATION:\s*NO/.test(raw),geometryNotReady=/RAW GEOMETRY:\s*NOT READY/.test(raw),blocked=/QUALITY GATE:\s*BLOCK/.test(raw),degraded=/DATA:\s*DEGRADED/.test(raw);
    const thesis=$('auThesis');
    if(degraded)setText(thesis,'Market data is degraded. ATLAS keeps the canonical decision at WAIT until reliable analysis data is restored.');
    else if(unqualified)setText(thesis,`${['LONG','SHORT'].includes(direction)?direction+' direction is developing, but ':''}the canonical 4–12H setup is not yet qualified. WAIT remains the only valid analysis.`);
    else if(geometryNotReady)setText(thesis,'Directional evidence is present, but verified Entry / Stop / Target geometry is not ready. Canonical decision remains WAIT.');
    else if(blocked)setText(thesis,'The base setup is evidence-blocked by the current setup-family quality gate. Canonical decision remains WAIT.');
    const steps=[];
    if(unqualified)steps.push('Canonical qualification must become YES');
    if(geometryNotReady)steps.push('Entry / Stop / Target geometry must become valid');
    if(blocked)steps.push('Evidence block must clear through setup reclassification or independent revalidation');
    if(degraded)steps.unshift('Reliable market data must be restored');
    if(steps.length)setText($('auTrigger'),steps.join(' · '));
    if(risk){let html=risk.innerHTML.replace(/Live execution disabled/gi,'Analysis only · no order routing');if(html!==risk.innerHTML)risk.innerHTML=html}
    $('auTrigger')?.closest('.au-trigger')?.classList.add('au-trigger-pending');
  }
  function polish(){polishScalar('auEntry');polishScalar('auStop');polishScalar('auTp1');polishTargets();polishTextNumbers('auTrigger');polishTextNumbers('auInvalidation');waitSemantics()}
  const style=document.createElement('style');style.id='atlasUnifiedTerminalPolishStyle';style.textContent=`#atlasUnified .au-target-stack{display:flex;flex-direction:column;gap:3px;white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.25}#atlasUnified .au-target-stack small{font-size:12px;font-weight:700;color:var(--au-muted,#94a3b8)}#atlasUnified .au-tile b{font-variant-numeric:tabular-nums}#atlasUnified .au-trigger-pending{border-color:#4b4530;background:rgba(45,35,14,.42)}#atlasUnified .au-trigger-pending .au-label{color:#f1c75b}@media(max-width:820px){#atlasUnified .au-target-tile{grid-column:span 2}#atlasUnified .au-tile{min-width:0}#atlasUnified .au-tile b{font-size:14px}}`;
  const old=$('atlasUnifiedTerminalPolishStyle');if(old)old.replaceWith(style);else document.head.appendChild(style);
  let scheduled=false;const schedule=()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;polish()})};const start=()=>{schedule();new MutationObserver(schedule).observe($('atlasUnified')||document.body,{subtree:true,childList:true,characterData:true})};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
