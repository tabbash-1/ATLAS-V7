"""Prospective market-direction state recorder. Research/shadow only.

Uses only fields frozen in the current canonical Production snapshot plus prior
records captured by this recorder. Missing evidence fails closed; no legacy
nearest-time joins or retrospective reconstruction.
"""
from __future__ import annotations
import datetime as dt, hashlib, json
from pathlib import Path
from market_breadth_exhaustion_research import assess as exhaustion
from breadth_reversal_caution_research import assess as reversal

SCHEMA="ATLAS_DIRECTION_STATE_FORWARD_SHADOW_V1"

def _f(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def _btc_features(snapshot):
    d=(snapshot.get("decisions") or {}).get("BTCUSDT") or {}
    # Accept only explicit point-in-time fields already frozen in canonical snapshot.
    rsi=_f(d.get("rsi14") or (d.get("indicators") or {}).get("rsi14") or (d.get("technical") or {}).get("rsi14"))
    mom=_f(d.get("momentum_24h_pct") or (d.get("indicators") or {}).get("momentum_24h_pct") or (d.get("technical") or {}).get("momentum_24h_pct"))
    trend=str(d.get("trend") or (d.get("independent_market_regime") or {}).get("trend") or (d.get("technical") or {}).get("trend") or "").upper()
    return {"rsi14":rsi,"momentum_24h_pct":mom,"trend":trend or None}

def _bullish_ratio(snapshot):
    votes=[]
    for d in (snapshot.get("decisions") or {}).values():
        if not isinstance(d,dict) or not d.get("ok"):continue
        x=str(d.get("candidate_direction") or d.get("product_direction") or "").upper()
        if x in {"LONG","SHORT"}:votes.append(x)
    return (sum(x=="LONG" for x in votes)/len(votes),len(votes)) if votes else (None,0)

def _previous(history):
    p=Path(history)
    if not p.exists():return None
    for line in reversed(p.read_text().splitlines()):
        try:
            x=json.loads(line)
            if x.get("schema")==SCHEMA:return x
        except Exception:pass
    return None

def capture(snapshot_path="status/atlas-production-latest.json",history_path="status/history/direction-state-forward-shadow.jsonl"):
    s=json.loads(Path(snapshot_path).read_text()); captured=s.get("captured_at")
    br,n=_bullish_ratio(s); btc=_btc_features(s); prev=_previous(history_path)
    prev_br=_f((prev or {}).get("bullish_ratio"))
    lost=max(0.0,prev_br-br) if prev_br is not None and br is not None else None
    drsi=None
    if prev and _f((prev.get("btc") or {}).get("rsi14")) is not None and btc["rsi14"] is not None:
        drsi=btc["rsi14"]-_f(prev["btc"]["rsi14"])
    ex=exhaustion(bullish_ratio=br,btc_trend=btc["trend"],btc_rsi14=btc["rsi14"],btc_momentum_24h_pct=btc["momentum_24h_pct"])
    rv=reversal(previous_bullish_ratio=prev_br,bullish_ratio=br,lost_bullish_ratio=lost,btc_rsi_delta=drsi)
    missing=[]
    if br is None:missing.append("BREADTH")
    if btc["rsi14"] is None:missing.append("BTC_RSI14")
    if btc["momentum_24h_pct"] is None:missing.append("BTC_MOMENTUM_24H")
    row={"schema":SCHEMA,"captured_at":captured,"bullish_ratio":br,"breadth_sample_n":n,"btc":btc,
         "previous_bullish_ratio":prev_br,"lost_bullish_ratio":lost,"btc_rsi_delta":drsi,
         "exhaustion":ex,"reversal":rv,"evidence_complete":not missing,"missing_evidence":missing,
         "state": ex["state"] if ex["eligible"] else (rv["state"] if rv["eligible"] else ("OBSERVE" if not missing else "MISSING_EVIDENCE")),
         "research_only":True,"shadow_only":True,"paper_only":True,"live_execution":False,
         "can_override_production":False,"can_override_final_gate":False,"can_change_threshold":False}
    key=f"{captured}|{br}|{btc['rsi14']}|{btc['momentum_24h_pct']}"
    row["observation_id"]=hashlib.sha256(key.encode()).hexdigest()[:24]
    hp=Path(history_path);hp.parent.mkdir(parents=True,exist_ok=True)
    known=set()
    if hp.exists():
        for line in hp.read_text().splitlines():
            try:known.add(json.loads(line).get("observation_id"))
            except Exception:pass
    if row["observation_id"] not in known:
        with hp.open("a",encoding="utf-8") as f:f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
    latest={"schema":SCHEMA+"_LATEST","generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"observation":row,
            "research_only":True,"live_execution":False,"can_override_production":False,"production_threshold_unchanged":68}
    Path("status/direction-state-forward-shadow-latest.json").write_text(json.dumps(latest,indent=2,sort_keys=True))
    return latest
if __name__=="__main__":print(json.dumps(capture(),sort_keys=True))
