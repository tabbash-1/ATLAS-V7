(function(){
  const VERSION='ATLAS_PRODUCTION_DECISION_UI_V1';
  const SUPPORTED=new Set(['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT']);

  function symbolOf(asset){
    return String(asset?.symbol||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');
  }

  function mapDecision(d){
    const signal=d.decision==='LONG'?'BUY':d.decision==='SHORT'?'SELL':'WAIT';
    const candidate=d.candidate_direction||'NONE';
    const reason=d.wait_reason||'SIGNAL_QUALIFIED';
    return {
      signal,
      confidence:d.score,
      score:d.score,
      entry:d.entry,
      stop_loss:d.stop_loss,
      target:d.take_profit,
      risk_reward:d.risk_reward,
      engine:{
        trend:d.regime||candidate,
        momentum:`Votes L${d.direction_votes_long}/S${d.direction_votes_short}`,
        volume:d.relative_volume==null?'—':`RV ${Number(d.relative_volume).toFixed(2)}`,
        structure:signal==='WAIT'?reason:(d.playbook||'SIGNAL_QUALIFIED')
      },
      indicators:d.indicators||{},
      production_decision:d
    };
  }

  async function productionAnalyze(){
    const state=window.ATLAS_APP_STATE;
    const asset=state?.assets?.[state.active];
    const symbol=symbolOf(asset);
    if(!SUPPORTED.has(symbol)) return false;

    const btn=document.getElementById('analyzeBtn');
    const badge=document.getElementById('engineBadge');
    const label=document.getElementById('providerLabel');
    if(btn) btn.disabled=true;
    if(window.setPill&&badge) window.setPill(badge,'PRODUCTION','working');
    if(label) label.textContent='Reading ATLAS Production decision…';

    try{
      const res=await fetch(`/api/decision/current?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'});
      const data=await res.json();
      if(!res.ok||!data.ok) throw new Error(data.error||`Production decision HTTP ${res.status}`);
      const result=mapDecision(data);
      window.ATLAS_LATEST_BASE=result;
      window.ATLAS_PRODUCTION_DECISION=data;
      const key=window.resultKey?window.resultKey():`${asset.symbol}|${state.interval}`;
      state.liveResults[key]={provider:'ATLAS Production · Single Source of Truth',result,confluence:null,time:Date.now(),production:true};
      if(window.applySignal) window.applySignal(result,`ATLAS Production · ${data.scoring_version||data.source} · ${new Date(data.generated_at).toLocaleString()}`);
      if(window.resetConfluence) window.resetConfluence();
      if(label){
        const detail=data.decision==='WAIT'
          ? `WAIT verified · ${data.wait_reason} · candidate ${data.candidate_direction||'none'} · score ${data.score??'—'}/${data.signal_threshold}`
          : `${data.decision} verified · score ${data.score}/${data.signal_threshold} · ${data.playbook||'production signal'}`;
        label.textContent=`ATLAS Production · ${detail}`;
      }
      if(window.setPill&&badge) window.setPill(badge,'PRODUCTION LIVE',data.decision==='WAIT'?'neutral':'buy');
      return true;
    }catch(err){
      console.error('[ATLAS production decision]',err);
      if(label) label.textContent=`Production unavailable · local analysis is not authoritative · ${err.message}`;
      if(window.setPill&&badge) window.setPill(badge,'PROD ERROR','sell');
      throw err;
    }finally{
      if(btn) btn.disabled=false;
    }
  }

  function install(){
    const btn=document.getElementById('analyzeBtn');
    if(!btn||btn.dataset.productionDecisionInstalled==='1') return;
    const original=btn.onclick;
    btn.dataset.productionDecisionInstalled='1';
    btn.onclick=async function(ev){
      const state=window.ATLAS_APP_STATE;
      const asset=state?.assets?.[state.active];
      if(SUPPORTED.has(symbolOf(asset))){
        try{ await productionAnalyze(); }
        catch(_){ /* Never silently substitute a local WAIT for a failed Production read. */ }
        return;
      }
      if(typeof original==='function') return original.call(this,ev);
      if(typeof window.analyzeActive==='function') return window.analyzeActive();
    };
    window.ATLAS_PRODUCTION_DECISION_UI={version:VERSION,analyze:productionAnalyze,supported:[...SUPPORTED]};
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
