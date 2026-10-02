"""True path-based outcome dataset for ATLAS research shadow.

Decision features are frozen at t. Outcome labels inspect only t+1..t+12.
Same-candle TP+SL ambiguity is conservatively a loss. Neither-hit remains
explicit and is excluded from binary model fit while reported as coverage.
"""
from __future__ import annotations
import profitability_prediction_engine as de
import profitability_prediction_historical_eval as he
import profitability_trade_outcome_predictor as op\nimport profitability_true_path_metrics as tm

VERSION="ATLAS_TRUE_PATH_OUTCOME_DATASET_V1"

def path_label(sample, future):
    side=sample["side"]
    y=op.outcome(sample["entry"],sample["atr"],side,future)
    return y

def build_symbol_samples(symbol,days,end_ms,btc=None):
    base=he.samples(symbol,days,end_ms,btc)
    # Fetch once; labels use strictly later candles.
    import historical_core_4_12h_replay as core
    rows=core.fetch_1h(symbol,days,end_ms)
    idx={r["t"]:i for i,r in enumerate(rows)}
    out=[]
    for z in base:
        i=idx.get(z["t"])
        if i is None: continue
        q={"t":z["t"],"symbol":symbol,"entry":z["entry"],"atr":z["atr"],"x":z["x"],
           "future":rows[i+1:i+13]}
        if len(q["future"])<12: continue
        out.append(q)
    return out

def training(end_ms,syms,days=180):
    raw=[]
    for s in syms: raw+=build_symbol_samples(s,days,end_ms)
    raw.sort(key=lambda z:z["t"])
    # Purge last 12h from the fit boundary so no label crosses it.
    split=int(len(raw)*.60)
    cutoff=raw[split-1]["t"] if split else 0
    fit_rows=[z for z in raw if z["t"]<=cutoff-12*3600000]
    dm=de.fit([{"t":z["t"],"x":z["x"],"y":de.label(z["entry"],z["future"],z["atr"])} for z in fit_rows])
    binary=[]; unresolved=0
    for z in fit_rows:
        p=de.predict(dm,z["x"]);side=p["prediction"]
        if side not in ("UP","DOWN"): continue
        row=dict(z,side=side)
        y=path_label(row,z["future"])
        if y is None: unresolved+=1;continue
        binary.append({"x":op.vector(z["x"],side,p["confidence"]),"y":y})
    return dm,op.fit(binary),{"fit_rows":len(fit_rows),"binary_rows":len(binary),"unresolved":unresolved,
      "purge_hours":tm.PURGE_HOURS,"embargo_hours":tm.EMBARGO_HOURS,"label":"TP_BEFORE_SL_PATH","same_candle":"LOSS","round_trip_cost_bps":tm.ROUND_TRIP_COST_BPS}

def safety():
    return {"research_only":True,"production_impact":"NONE","threshold":68,
      "label_uses_post_cutoff_candles_only":True,"same_candle_tp_sl":"LOSS",
      "purge_hours":tm.PURGE_HOURS,"embargo_hours":tm.EMBARGO_HOURS,"round_trip_cost_bps":tm.ROUND_TRIP_COST_BPS,"can_override_final_gate":False}
