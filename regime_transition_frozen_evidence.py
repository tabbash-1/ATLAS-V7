"""Prospective frozen evidence recorder for Regime Transition Challenger V1.

Research/shadow only. Captures only evidence present in the canonical Production
snapshot at decision time. No retrospective recomputation is allowed.
"""
from __future__ import annotations
import datetime as dt, hashlib, json
from pathlib import Path
from regime_transition_challenger import assess
from transition_quality_research import assess as assess_transition_quality

SCHEMA="ATLAS_REGIME_TRANSITION_FROZEN_EVIDENCE_V1"

def _u(v): return str(v or "").strip().upper()
def _f(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def _regime_from_decision(d):
    # Freeze only an explicitly emitted independent regime. Legacy/signal-derived
    # regime labels receive no credit.
    r=d.get("independent_market_regime") or d.get("market_regime_independent")
    return r if isinstance(r,dict) else None

def _frames(d):
    t=d.get("htf_thesis") or {}
    fs=t.get("frames") or {}
    return {k:{"bias":_u((fs.get(k) or {}).get("bias"))} for k in ("1h","4h","12h","1d")}

def _breadth(snapshot,candidate):
    decisions=snapshot.get("decisions") or {}
    votes=[]
    for d in decisions.values():
        if not isinstance(d,dict) or not d.get("ok"):continue
        x=_u(d.get("candidate_direction") or d.get("product_direction"))
        if x in {"LONG","SHORT"}:votes.append(x)
    if not votes:return None
    aligned=sum(x==candidate for x in votes)
    return {"direction":candidate if aligned/len(votes)>=.5 else ("SHORT" if candidate=="LONG" else "LONG"),
            "aligned_ratio":round(aligned/len(votes),6),"sample_n":len(votes),
            "source":"FROZEN_CANONICAL_SNAPSHOT_CANDIDATE_BREADTH"}

def _derivatives(d,candidate):
    if d.get("futures_available") is not True:return None
    direction=_u(d.get("futures_direction") or d.get("derivatives_direction"))
    if direction not in {"LONG","SHORT"}:
        score=_f(d.get("futures_score"))
        if score is not None: direction=candidate if score>=0 else ("SHORT" if candidate=="LONG" else "LONG")
    if direction not in {"LONG","SHORT"}:return None
    return {"direction":direction,"crowded":bool(d.get("futures_crowded") or d.get("derivatives_crowded")),
            "provider":d.get("futures_provider"),"source":"FROZEN_PRODUCTION_FUTURES_EVIDENCE"}

def freeze(snapshot):
    captured=snapshot.get("captured_at")
    decisions=snapshot.get("decisions") or {}
    btc_decision=decisions.get("BTCUSDT") or {}
    btc=btc_decision.get("independent_btc_regime") or _regime_from_decision(btc_decision)
    out=[]
    for symbol,d in decisions.items():
        if not isinstance(d,dict) or not d.get("ok"):continue
        truth=d.get("canonical_decision") or {}
        if truth.get("source_of_truth")!="FINAL_TRADE_GATE" or truth.get("trade_ready") is True:continue
        candidate=_u(d.get("candidate_direction") or d.get("product_direction"))
        if candidate not in {"LONG","SHORT"}:continue
        plan=d.get("trade_plan") or {}
        entry=_f(plan.get("entry") or d.get("entry"))
        stop=_f(plan.get("stop_loss") or d.get("stop_loss"))
        tp2=_f(plan.get("tp2") or d.get("take_profit"))
        row={"candidate_direction":candidate,"canonical_product_decision":"WAIT",
             "wait_reason":truth.get("raw_wait_reason") or truth.get("wait_reason"),
             "htf_thesis":{"frames":_frames(d)},
             "htf_core_geometry":{"ready":bool((d.get("geometry_gate") or {}).get("qualified"))},
             "analyst_output":{"risk_reward":_f(plan.get("rr_tp2") or d.get("risk_reward")),
                                "entry":entry,"stop_loss":stop}}
        asset=_regime_from_decision(d)
        breadth=_breadth(snapshot,candidate)
        derivatives=_derivatives(d,candidate)
        # Fail closed: missing independent regime evidence is recorded, never reconstructed.
        verdict=assess(row,asset or {},btc or {},breadth,derivatives)
        key=f"{truth.get('decision_id')}|{captured}|{symbol}|{candidate}"
        out.append({"schema":SCHEMA,"observation_id":hashlib.sha256(key.encode()).hexdigest()[:24],
          "captured_at":captured,"decision_id":truth.get("decision_id"),"symbol":symbol,
          "canonical_decision":"WAIT","candidate_direction":candidate,
          "frozen_evidence":{"asset_regime":asset,"btc_regime":btc,"breadth":breadth,"derivatives":derivatives,
                             "frames":_frames(d),"geometry_ready":row["htf_core_geometry"]["ready"],
                             "rr_tp2":row["analyst_output"]["risk_reward"],"net_rr_after_locked_cost":verdict.get("net_rr_after_locked_cost"),
                             "locked_cost_bps_12h":verdict.get("locked_cost_bps_12h"),
                             "entry":entry,"stop_loss":stop,"tp2":tp2},
          "challenger":verdict,"transition_quality":assess_transition_quality({"candidate_direction":candidate,"frozen_evidence":{"asset_regime":asset,"btc_regime":btc,"breadth":breadth,"derivatives":derivatives,"frames":_frames(d),"net_rr_after_locked_cost":verdict.get("net_rr_after_locked_cost")}}),"research_only":True,"paper_only":True,"live_execution":False,
          "can_override_production":False,"production_threshold_unchanged":68})
    return out

def capture(snapshot_path="status/atlas-production-latest.json",history_path="status/history/regime-transition-frozen-evidence.jsonl"):
    snapshot=json.loads(Path(snapshot_path).read_text())
    rows=freeze(snapshot); hp=Path(history_path); hp.parent.mkdir(parents=True,exist_ok=True)
    known=set()
    if hp.exists():
        for line in hp.read_text().splitlines():
            try: known.add(json.loads(line).get("observation_id"))
            except Exception: pass
    with hp.open("a",encoding="utf-8") as f:
        for x in rows:
            if x["observation_id"] not in known:f.write(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n")
    latest={"schema":"ATLAS_REGIME_TRANSITION_FROZEN_BUNDLE_V1","generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "observations":rows,"research_only":True,"live_execution":False,"can_override_production":False,
            "production_threshold_unchanged":68}
    Path("status/regime-transition-frozen-latest.json").write_text(json.dumps(latest,indent=2,sort_keys=True))
    return latest

if __name__=="__main__": print(json.dumps(capture(),sort_keys=True))
