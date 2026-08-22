(function(){
const $=id=>document.getElementById(id);
function activeSymbol(){return (window.ATLAS_STATE?.selectedAsset?.symbol||'BINANCE:BTCUSDT').replace('BINANCE:','');}
function fmt(v,d=3){return v==null||!Number.isFinite(Number(v))?'—':Number(v).toFixed(d);}
function pct(v){return v==null||!Number.isFinite(Number(v))?'—':`${Number(v).toFixed(2)}%`;}
function pill(el,text,kind='neutral'){if(!el)return;el.textContent=text;el.className=`pill ${kind}`;}
function row(f){
  const n=Number(f?.n||0),delta=Number(f?.delta_vs_baseline_avg_pct),avg=f?.avg_return_pct,hit=f?.hit_rate_pct;
  const status=n>=30?'STRONGER SAMPLE':n>=15?'EARLY SIGNAL':'SMALL SAMPLE';
  const kind=n>=30?'buy':n>=15?'working':'neutral';
  return `<tr><td>${String(f?.tag||'—')}</td><td>${n}</td><td>${pct(avg)}</td><td>${pct(hit)}</td><td>${pct(Number.isFinite(delta)?delta:null)}</td><td><span class="pill ${kind}">${status}</span></td></tr>`;
}
function renderList(id,list,empty){const body=$(id);if(!body)return;body.innerHTML=(list&&list.length)?list.map(row).join(''):`<tr><td colspan="6">${empty}</td></tr>`;}
function render(data){
 const baseline=data?.baseline||{}, matured=Number(data?.matured||0), minN=Number(data?.minimum_group_n||5);
 pill($('learningBadge'),matured>=100?'VALIDATION READY':matured>=30?'EARLY RESEARCH':'COLLECTING',matured>=100?'buy':matured>=30?'working':'neutral');
 $('learningMetrics').innerHTML=[['Matured 24h',matured],['Baseline avg',pct(baseline.avg_return_pct)],['Baseline hit rate',pct(baseline.hit_rate_pct)],['Factor groups',data?.factors?.length||0],['Minimum group N',minN],['Weight changes','DISABLED']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('');
 renderList('learningStrongBody',data?.strongest_associations,'No factor has enough matured observations yet.');
 renderList('learningWeakBody',data?.weakest_associations,'No factor has enough matured observations yet.');
 $('learningNotes').textContent=matured<30?'ATLAS is collecting evidence. Factor associations are descriptive only and too small for weight changes.':matured<100?'Early research stage: useful patterns may appear, but no automatic weight changes are permitted.':'Validation sample reached. Factors may now become candidates for controlled out-of-sample testing, never direct live promotion.';
}
async function refresh(){pill($('learningBadge'),'CHECKING','working');try{const r=await fetch(`/api/ai/attribution?symbol=${encodeURIComponent(activeSymbol())}&horizon=24&min_n=5`,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);render(await r.json());}catch(e){pill($('learningBadge'),'UNAVAILABLE','neutral');$('learningNotes').textContent=`Learning endpoint unavailable: ${e.message}`;}}
function init(){if(!$('learningMetrics'))return;$('learningRefreshBtn')?.addEventListener('click',refresh);refresh();setInterval(refresh,60000);}
window.refreshAtlasLearning=refresh;if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();