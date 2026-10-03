(()=>{const id='onDemandAnalysisEvidenceCard';if(document.getElementById(id))return;
const host=document.querySelector('.main');if(!host)return;
const card=document.createElement('section');card.id=id;card.className='card metrics-card';card.innerHTML=`
<div class="card-head"><div><strong>ON-DEMAND ANALYSIS EVIDENCE</strong><div class="muted small">When asked now: LONG / SHORT / WAIT · 4H / 8H / 12H · Research evidence only</div></div><span id="odaBadge" class="pill neutral">LOADING</span></div>
<div id="odaMetrics" class="trial-grid"><div><span>Status</span><b>Loading benchmark</b></div></div>
<div id="odaNotes" class="comparison-box muted small">This benchmark cannot override FINAL_TRADE_GATE or Production.</div>`;
const ref=document.getElementById('profitabilityShadowCard');if(ref)ref.parentNode.insertBefore(card,ref);else host.appendChild(card);
const f=v=>v==null?'—':Number(v).toFixed(2)+'%';
fetch('/api/research/on-demand-analysis-benchmark',{cache:'no-store'}).then(r=>r.json()).then(d=>{
 const b=document.getElementById('odaBadge'),m=document.getElementById('odaMetrics'),n=document.getElementById('odaNotes');
 if(!d||d.ok===false||!d.overall){b.textContent='COLLECTING';m.innerHTML='<div><span>Status</span><b>No committed benchmark yet</b></div>';return;}
 b.textContent='EVIDENCE';b.className='pill working';
 const L=d.overall.legacy_1h||{},H=d.overall.htf_consensus||{};
 m.innerHTML=[4,8,12].map(h=>{const a=L[h+'h']||{},x=H[h+'h']||{};return `<div><span>${h}H HTF accuracy</span><b>${f(x.accuracy_pct)}</b><small>1H: ${f(a.accuracy_pct)} · WAIT ${f(x.wait_rate_pct)} · missed ${f(x.missed_directional_move_pct)}</small></div>`}).join('');
 n.textContent='Point-in-time benchmark. Research only; no Production threshold or decision is changed.';
}).catch(()=>{const b=document.getElementById('odaBadge');if(b)b.textContent='UNAVAILABLE';});})();