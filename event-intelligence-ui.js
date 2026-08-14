(() => {
const $=id=>document.getElementById(id);
function currentSymbol(){return String(window.ATLAS_STATE?.selectedAsset?.symbol||'BINANCE:BTCUSDT').replace(/^BINANCE:/,'').toUpperCase();}
function fmt(v,d=1){return v==null?'—':Number(v).toFixed(d);}
function relevantEvent(x,sym){return (x.scope||'MARKET')==='MARKET'||x.symbol===sym;}
async function refresh(){
 const badge=$('eventRadarBadge'),body=$('eventRadarBody'),stats=$('eventStats'),sourcesEl=$('eventSources'); if(!body)return;
 try{
   const sym=currentSymbol();
   const [ev,st,rx,src,surpriseStats]=await Promise.all([
     fetch('/api/events/latest').then(r=>r.json()),
     fetch('/api/events/stats').then(r=>r.json()),
     fetch('/api/events/reactions?limit=150').then(r=>r.json()),
     fetch('/api/news/sources').then(r=>r.json()),
     fetch('/api/events/surprise-stats').then(r=>r.json())
   ]);
   const reactionMap=new Map((rx.records||[]).map(x=>[x.fingerprint||`${x.title}|${x.event_at_ms}`,x.reaction||{}]));
   const rows=(ev.events||[]).filter(x=>relevantEvent(x,sym)).slice(-10).reverse();
   body.innerHTML=rows.length?rows.map(x=>{
     const k=x.fingerprint||`${x.title}|${x.event_at_ms}`,r=reactionMap.get(k)||{};
     return `<tr><td>${new Date(x.event_at_ms||x.captured_at_ms).toLocaleString()}</td><td>${x.event_type||'OTHER'}</td><td>${x.title}<small>${x.source||'Manual'}${x.auto_ingested?' · AUTO':''}</small></td><td>${fmt(x.impact_score,0)}</td><td>${x.direction||'UNCLEAR'}</td><td>${r.available?(r.label||'—'):'WAITING'}</td><td>${r.early_return_pct==null?'—':fmt(r.early_return_pct,2)+'%'}</td></tr>`;
   }).join(''):'<tr><td colspan="7">No relevant shadow events recorded yet.</td></tr>';
   const types=st.types||[], matured1=types.reduce((a,t)=>a+Number(t.horizons?.['1']?.n||0),0),matured24=types.reduce((a,t)=>a+Number(t.horizons?.['24']?.n||0),0);
   const sg=surpriseStats.groups||[],sn=sg.reduce((a,x)=>a+Number(x.n||0),0); stats.textContent=`${st.events||0} events · ${matured1} matured 1h · ${matured24} matured 24h · ${sn} economic-surprise records · news has ZERO weight in Final Score`;
   if(sourcesEl)sourcesEl.textContent=`Auto sources: ${(src.sources||[]).map(x=>x.name).join(' · ')} · poll ${Math.round((src.poll_seconds||600)/60)} min`;
   badge.textContent=rows.length?`${rows.length} RELEVANT`:'SHADOW READY';badge.className='pill neutral';
 }catch(e){badge.textContent='OFFLINE';badge.className='pill sell';if(stats)stats.textContent=e.message;}
}
async function syncNews(){
 const btn=$('eventSyncBtn'),preview=$('eventPreview');if(btn)btn.disabled=true;
 try{
   if(preview)preview.textContent='Syncing official primary-source feeds…';
   const r=await fetch('/api/news/ingest',{method:'POST'}),j=await r.json();
   if(!r.ok)throw new Error(j.error||'News sync failed');
   const errs=(j.errors||[]).map(x=>`${x.source}: ${x.error}`).join(' · ');
   if(preview)preview.innerHTML=`<b>Auto ingest:</b> ${j.stored||0} new unique events${errs?` · Source warnings: ${errs}`:''} · SHADOW ONLY`;
   await refresh();
 }catch(e){if(preview)preview.textContent=e.message;}
 finally{if(btn)btn.disabled=false;}
}
async function record(){
 const title=$('eventTitle')?.value.trim();if(!title)return;
 const ev={title,summary:$('eventSummary')?.value.trim()||'',type:$('eventType')?.value||'OTHER',
   source:$('eventSource')?.value.trim()||'MANUAL',source_tier:$('eventSourceTier')?.value||'UNKNOWN',
   confirmed:$('eventConfirmed')?.checked||false,scope:$('eventScope')?.value||'MARKET'};
 const scored=ATLAS_EVENT_INTELLIGENCE.scoreEvent(ev);
 const actual=Number($('eventActual')?.value),consensus=Number($('eventConsensus')?.value),previous=Number($('eventPrevious')?.value),scale=Number($('eventScale')?.value);
 const surprise=(Number.isFinite(actual)&&Number.isFinite(consensus))?ATLAS_EVENT_SURPRISE.scoreEconomicSurprise({eventType:scored.type,actual,consensus,previous:Number.isFinite(previous)?previous:null,scale:Number.isFinite(scale)&&scale>0?scale:null}):null;
 const fut=window.ATLAS_LATEST_FUTURES||null,con=window.ATLAS_LATEST_CONFLUENCE||null;
 const payload={...ev,symbol:currentSymbol(),event_type:scored.type,impact_score:scored.impact_score,sentiment_score:scored.sentiment_score,direction:scored.direction,
   futures_score:fut?.score,futures_bias:fut?.bias,funding_rate:fut?.funding_rate,oi_change_pct:fut?.oi_change_pct,taker_ratio:fut?.taker_ratio,orderbook_imbalance:fut?.orderbook_imbalance,
   relative_volume:con?.volume?.relative_volume,volume_quality:con?.volume?.quality_score,
   actual:surprise?.actual,consensus:surprise?.consensus,previous:surprise?.previous,surprise_scale:surprise?.scale,
   normalized_surprise:surprise?.normalized_surprise,surprise_magnitude:surprise?.surprise_magnitude,surprise_risk_direction:surprise?.risk_direction};
 const r=await fetch('/api/events/observe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),j=await r.json();
 if(!r.ok)throw new Error(j.error||'Could not store event');
 $('eventPreview').innerHTML=`<b>${scored.type}</b> · Impact ${scored.impact_score}/100 · ${scored.direction}${surprise?.available?` · Surprise ${surprise.normalized_surprise}σ-like · ${surprise.risk_direction}`:''} · MANUAL SHADOW EVENT`;
 $('eventTitle').value='';$('eventSummary').value='';await refresh();
}
$('eventRecordBtn')?.addEventListener('click',()=>record().catch(e=>{$('eventPreview').textContent=e.message;}));
$('eventRefreshBtn')?.addEventListener('click',refresh);
$('eventSyncBtn')?.addEventListener('click',syncNews);
window.refreshEventRadar=refresh;
setTimeout(refresh,1400);
setInterval(refresh,120000);
})();