(function(){
  const DEFAULTS={fee_bps_per_side:10,slippage_bps_per_side:5};
  function n(v){const x=Number(v);return Number.isFinite(x)?x:null;}
  function evaluate(row,opts={}){
    const entry=n(row?.entry), sl=n(row?.geometry?.stop_loss), tp1=n(row?.geometry?.take_profit_1);
    const dir=String(row?.direction||'').toUpperCase();
    const feeBps=n(opts.fee_bps_per_side)??DEFAULTS.fee_bps_per_side;
    const slipBps=n(opts.slippage_bps_per_side)??DEFAULTS.slippage_bps_per_side;
    if(!entry||!sl||!tp1||!['LONG','SHORT'].includes(dir))return {...row,execution_model:null};
    const risk=Math.abs(entry-sl), riskPct=risk/entry*100;
    if(risk<=0)return {...row,execution_model:null};
    const roundTripCostPct=2*(feeBps+slipBps)/100;
    const grossWinPct=Math.abs(tp1-entry)/entry*100;
    const grossLossPct=-riskPct;
    let grossPct=null, grossR=null;
    if(row.status==='WIN'){grossPct=grossWinPct;grossR=grossWinPct/riskPct;}
    else if(row.status==='LOSS'){grossPct=grossLossPct;grossR=-1;}
    const netPct=grossPct==null?null:grossPct-roundTripCostPct;
    const netR=netPct==null?null:netPct/riskPct;
    return {...row,execution_model:{fee_bps_per_side:feeBps,slippage_bps_per_side:slipBps,round_trip_cost_pct:roundTripCostPct,risk_pct:riskPct,gross_pct:grossPct,gross_r:grossR,net_pct:netPct,net_r:netR}};
  }
  window.ATLAS_PAPER_EXECUTION={DEFAULTS,evaluate};
})();