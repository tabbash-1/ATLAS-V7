(function(){
  const VERSION='ATLAS_PRODUCTION_DECISION_UI_V3';
  const SUPPORTED=new Set(['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT']);

  function symbolOf(asset){
    return String(asset?.symbol||'').toUpperCase().replace('BINANCE:','').replace(/[^A-Z0-9]/g,'');
  }

  function signed(v){
    const n=Number(v||0);
    return `${n>=0?'+':''}${Number.isInteger(n)?n:n.toFixed(1)}`;
  }

  function attributionText(d){
    const a=d?.score_attribution;
    if(!a) return '';
    return `base ${a.trend_base} · vol ${signed(a.volume_bonus)} · RS ${signed(a.relative_strength_adjustment)} · futures ${signed(a.futures_adjustment)} · obstacle ${signed(a.obstacle_adjustment)} = ${a.final_score}`;
  }

  function mapDecision(d,base={}){
    const signal=d.decision==='LONG'?'BUY':d.decision==='SHORT'?'SELL':'WAIT';
    const candidate=d.candidate_direction||'NONE';
    const reason=d.wait_reason||'SIGNAL_QUALIFIED';
    const attr=attributionText(d);
    return {
      ...base,
      signal,
      confidence:d.score,
      score:d.score,
      entry:d.entry,
      stop_loss:d.stop_loss,
      stop:d.stop_loss,
      target:d.take_profit,
      risk_reward:d.risk_reward,
      engine:{
        ...(base.engine||{}),
        trend:d.regime||candidate,
        momentum:`Votes L${d.direction_votes_long}/S${d.direction_votes_short}`,
        volume:d.relative_volume==null?(base.engine?.volume||'—'):`RV ${Number(d.relative_volume).toFixed(2)}`,
        structure:signal==='WAIT'?(attr?`${reason} · ${attr}`:reason):(d.playbook||'SIGNAL_QUALIFIED')
      },
      indicators:{...(base.indicators||{}),...(d.indicators||{})},
      production_decision:d
    };
  }

  async function productionVerify(){
    const state=window.ATLAS_APP_STATE;
    const asset=state?.assets?.[state.active];
    const symbol=symbolOf(asset);
    if(!SUPPORTED.has(symbol)) return false;

    const btn=document.getElementById('analyzeBtn');
    const badge=document.getElementById('engineBadge');
    const label=document.getElementById('providerLabel');
    if(btn) btn.disabled=true;
    if(window.setPill&&badge) window.setPill(badge,'VERIFYING','working');
    if(label) label.textContent='Verifying final decision with ATLAS Production…';

    const key=window.resultKey?window.resultKey():`${asset.symbol}|${state.interval}`;
    const existing=state.liveResults[key]||{};
    const existingResult=existing.result||window.ATLAS_LATEST_BASE||{};

    try{
      const res=await fetch(`/api/decision/current?symbol=${encodeURIComponent(symbol)}&t=${Date.now()}`,{cache:'no-store'});
      const data=await res.json();
      if(!res.ok||!data.ok) throw new Error(data.error||`Production decision HTTP ${res.status}`);

      const result=mapDecision(data,existingResult);
      window.ATLAS_LATEST_BASE=result;
      window.ATLAS_PRODUCTION_DECISION=data;
      state.liveResults[key]={
        ...existing,
        provider:'ATLAS Production verified',
        result,
        confluence:existing.confluence||window.ATLAS_LATEST_CONFLUENCE||null,
        time:Date.now(),
        production:true
      };

      if(window.applySignal) window.applySignal(result,`ATLAS Production verified · ${data.scoring_version||data.source} · ${new Date(data.generated_at).toLocaleString()}`);
      if(window.refreshTradeManagement) setTimeout(()=>window.refreshTradeManagement(result,state.liveResults[key].confluence),30);

      if(label){
        const attr=attributionText(data);
        const detail=data.decision==='WAIT'
          ? `WAIT verified · ${data.wait_reason} · candidate ${data.candidate_direction||'none'} · score ${data.score??'—'}/${data.signal_threshold}${attr?` · ${attr}`:''}`
          : `${data.decision} verified · score ${data.score}/${data.signal_threshold} · ${data.playbook||'production signal'}${attr?` · ${attr}`:''}`;
        label.textContent=`ATLAS Production · ${detail}`;
      }
      if(window.setPill&&badge) window.setPill(badge,'VERIFIED',data.decision==='WAIT'?'neutral':'buy');
      return true;
    }catch(err){
      console.error('[ATLAS production verification]',err);
      if(label) label.textContent=`Production verification unavailable · local analysis preserved · ${err.message}`;
      if(window.setPill&&badge) window.setPill(badge,'LOCAL ONLY','neutral');
      return false;
    }finally{
      if(btn) btn.disabled=false;
    }
  }

  function install(){
    const btn=document.getElementById('analyzeBtn');
    if(!btn||btn.dataset.productionDecisionInstalled==='3') return;
    const original=btn.onclick;
    btn.dataset.productionDecisionInstalled='3';

    btn.onclick=async function(ev){
      const state=window.ATLAS_APP_STATE;
      const asset=state?.assets?.[state.active];

      if(typeof original==='function') await original.call(this,ev);
      else if(typeof window.analyzeActive==='function') await window.analyzeActive();

      if(SUPPORTED.has(symbolOf(asset))) await productionVerify();
    };

    window.ATLAS_PRODUCTION_DECISION_UI={version:VERSION,verify:productionVerify,supported:[...SUPPORTED]};
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
