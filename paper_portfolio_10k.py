#!/usr/bin/env python3
"""ATLAS prospective $10K paper portfolio.

Causal, paper-only portfolio. It observes committed Production snapshots after a
frozen cohort start and enrolls only canonical TRADE READY transitions. It never
sends orders, changes Production, backfills pre-start trades, guesses ambiguous
paths, or zero-fills missing market data.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import pathlib
import time
from typing import Any

from offline_production_path_settlement import market_klines, event_from, excursions

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "status/paper-portfolio-10k-manifest.json"
HISTORY = ROOT / "status/history/production-snapshots.jsonl"
COHORT = ROOT / "status/history/paper-portfolio-10k-cohort.jsonl"
LATEST = ROOT / "status/paper-portfolio-10k-latest.json"
INTEGRITY = ROOT / "status/paper-portfolio-10k-integrity.json"
SCHEMA = "ATLAS_PAPER_PORTFOLIO_10K_V2_PRODUCT_WINDOW"
INTEGRITY_SCHEMA = "ATLAS_PAPER_PORTFOLIO_10K_INTEGRITY_V1"
PRODUCT_HORIZON = "4-12H"
PRODUCT_CHECKPOINT_HOURS = (4, 8, 12)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def parse_time(v: str) -> dt.datetime:
    x = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def load_manifest() -> dict[str, Any]:
    m = json.loads(MANIFEST.read_text())
    expected = str(m.get("manifest_hash") or "")
    body = dict(m); body.pop("manifest_hash", None)
    actual = sha(body)
    if not expected or actual != expected:
        raise RuntimeError(f"MANIFEST_LOCK_MISMATCH expected={expected} actual={actual}")
    if m.get("live_execution") is not False or m.get("paper_only") is not True:
        raise RuntimeError("PAPER_SAFETY_CONTRACT_BROKEN")
    return m


def load_jsonl(path: pathlib.Path):
    rows = []
    if not path.exists(): return rows
    for line in path.read_text().splitlines():
        if not line.strip(): continue
        try: rows.append(json.loads(line))
        except Exception as e: raise RuntimeError(f"INVALID_JSONL {path}: {e}")
    return rows


def load_snapshots(start: dt.datetime):
    out = []
    for row in load_jsonl(HISTORY):
        try: t = parse_time(row["captured_at"])
        except Exception: continue
        if t >= start: out.append((t, row))
    return sorted(out, key=lambda x: x[0])


def geometry(decision: dict[str, Any]):
    p = decision.get("trade_plan") or {}
    direction = str(p.get("direction") or decision.get("candidate_direction") or "").upper()
    entry, stop, tp1, tp2 = map(fnum, (p.get("entry"), p.get("stop_loss"), p.get("tp1"), p.get("tp2")))
    if direction not in {"LONG", "SHORT"} or None in (entry, stop, tp2): return None
    risk = abs(entry-stop)
    if risk <= 0: return None
    if direction == "LONG" and not (stop < entry < tp2): return None
    if direction == "SHORT" and not (stop > entry > tp2): return None
    if tp1 is None: tp1 = entry + risk if direction == "LONG" else entry - risk
    rr2 = fnum(p.get("rr_tp2")) or abs(tp2-entry)/risk
    return {"direction":direction,"entry":entry,"stop_loss":stop,"tp1":tp1,"tp2":tp2,
            "rr_tp2":rr2,"risk_abs":risk,"entry_mode":p.get("entry_mode"),"plan_version":p.get("version"),
            "product_horizon":p.get("product_horizon") or PRODUCT_HORIZON,
            "canonical_lane":p.get("canonical_lane") or "CORE_4_12H"}


def trade_ready(decision: dict[str, Any]) -> bool:
    p = decision.get("trade_plan") or {}
    action = str(decision.get("actionable_decision") or "").upper()
    return bool(decision.get("execution_ready") is True and p.get("can_execute") is True and action in {"LONG","SHORT"} and geometry(decision))


def event_id(symbol: str, captured_at: str, g: dict[str, Any]) -> str:
    return hashlib.sha256(f"{symbol}|{captured_at}|{g['direction']}|{g['entry']:.12g}|{g['stop_loss']:.12g}|{g['tp2']:.12g}".encode()).hexdigest()[:24]


def verify_append_only(rows: list[dict[str, Any]], previous: dict[str, Any] | None):
    hashes = [sha(r) for r in rows]
    if previous:
        old = previous.get("row_hashes") or []
        if len(hashes) < len(old) or hashes[:len(old)] != old:
            raise RuntimeError("COHORT_APPEND_ONLY_VIOLATION")
    return hashes


def previous_observed_through(manifest: dict[str, Any], prev_report: dict[str, Any] | None):
    if prev_report and prev_report.get("observed_through_at"):
        return parse_time(prev_report["observed_through_at"])
    return parse_time(manifest["cohort_start_at"]) - dt.timedelta(microseconds=1)


def previous_equity(manifest: dict[str, Any], prev_report: dict[str, Any] | None) -> float:
    if prev_report and fnum((prev_report.get("portfolio") or {}).get("equity_usd")) is not None:
        return float(prev_report["portfolio"]["equity_usd"])
    return float(manifest["starting_equity_usd"])


def enroll_new(manifest, cohort, snapshots, observed_through, sizing_equity):
    horizon = dt.timedelta(hours=float(manifest["holding_horizon_hours"]))
    max_positions = int(manifest["max_concurrent_positions"])
    risk_pct = float(manifest["risk_per_trade_pct"]) / 100.0
    ids = {r["id"] for r in cohort}
    active_state: dict[str, str | None] = {}
    for t, snap in snapshots:
        if t > observed_through: break
        for symbol, d in (snap.get("decisions") or {}).items():
            if trade_ready(d or {}): active_state[symbol] = geometry(d)["direction"]
            else: active_state[symbol] = None
    added = []
    newest = observed_through
    for t, snap in snapshots:
        if t <= observed_through: continue
        newest = max(newest, t)
        for symbol, d in (snap.get("decisions") or {}).items():
            d = d or {}; ready = trade_ready(d); g = geometry(d) if ready else None
            direction = g["direction"] if g else None
            prior = active_state.get(symbol)
            active_state[symbol] = direction
            if not ready or prior == direction: continue
            captured = t.isoformat(); eid = event_id(symbol, captured, g)
            if eid in ids: continue
            conservative_open = [r for r in cohort if parse_time(r["captured_at"]) <= t < parse_time(r["captured_at"]) + horizon]
            if len(conservative_open) >= max_positions:
                continue
            risk_usd = round(sizing_equity * risk_pct, 2)
            qty = risk_usd / g["risk_abs"]
            row = {
                "schema":"ATLAS_PAPER_PORTFOLIO_10K_ENTRY_V2","id":eid,"portfolio_id":manifest["portfolio_id"],
                "captured_at":captured,"captured_at_ms":int(t.timestamp()*1000),"symbol":symbol,"direction":direction,
                "decision_source":"COMMITTED_PRODUCTION_SNAPSHOT","decision_action":"TRADE_READY",
                "product_horizon":g.get("product_horizon") or PRODUCT_HORIZON,"canonical_lane":g.get("canonical_lane") or "CORE_4_12H",
                "evaluation_horizons":["4h","8h","12h"],
                "score":fnum(d.get("score")),"threshold":fnum(d.get("signal_threshold")),
                "geometry":g,"sizing_equity_usd":round(sizing_equity,2),"risk_pct":float(manifest["risk_per_trade_pct"]),
                "risk_usd":risk_usd,"paper_quantity":round(qty,12),"paper_notional_usd":round(abs(qty*g["entry"]),2),
                "outcome_known_at_entry":False,"paper_only":True,"live_execution":False,"can_override_production":False,
                "manifest_hash":manifest["manifest_hash"]
            }
            cohort.append(row); added.append(row); ids.add(eid)
    return added, newest


def checkpoint_entry(row: dict[str, Any], checkpoint_h: float, now_ms: int):
    start=int(row["captured_at_ms"]); checkpoint_ms=start+int(checkpoint_h*3600_000); g=row["geometry"]
    if now_ms < checkpoint_ms:
        return {"id":row["id"],"checkpoint_h":checkpoint_h,"status":"NOT_MATURED","matured":False,"r_multiple":None}
    try:
        candles, provider=market_klines(row["symbol"],"5",start,checkpoint_ms)
        if not candles: raise RuntimeError("no_5m_candles")
        ev,candle,tp1_seen=event_from(candles,g)
        if ev=="AMBIGUOUS" and candle:
            one,p1=market_klines(row["symbol"],"1",candle["open_time"],candle["open_time"]+5*60_000-1)
            ev1,c1,tp1_1=event_from(one,g)
            if ev1 in {"SL","TP2"}: ev,candle=ev1,c1 or candle
            else: ev="AMBIGUOUS"
            tp1_seen=tp1_seen or tp1_1; provider += "+1M:"+p1
        if ev=="SL": status,r="LOSS_BY_CHECKPOINT",-1.0
        elif ev=="TP2": status,r="TP2_BY_CHECKPOINT",float(g["rr_tp2"])
        elif ev=="AMBIGUOUS": status,r="AMBIGUOUS",None
        else:
            last=candles[-1]["close"]
            directional=(last-g["entry"]) if g["direction"]=="LONG" else (g["entry"]-last)
            r=directional/g["risk_abs"]; status="MARK_TO_MARKET"
        return {"id":row["id"],"checkpoint_h":checkpoint_h,"status":status,"matured":True,
                "r_multiple":None if r is None else round(float(r),4),"tp1_reached":bool(tp1_seen),"market_source":provider}
    except Exception as e:
        return {"id":row["id"],"checkpoint_h":checkpoint_h,"status":"MARKET_DATA_ERROR","matured":True,
                "r_multiple":None,"error":str(e)[:700]}


def settle_entry(row: dict[str, Any], horizon_h: float, now_ms: int):
    start = int(row["captured_at_ms"]); maturity = start + int(horizon_h*3600_000); g=row["geometry"]
    if now_ms < maturity:
        return {"id":row["id"],"status":"OPEN","terminal":False,"r_multiple":None,"exit_at_ms":None}
    try:
        candles, provider = market_klines(row["symbol"], "5", start, maturity)
        if not candles: raise RuntimeError("no_5m_candles")
        ev, candle, tp1_seen = event_from(candles, g)
        if ev == "AMBIGUOUS" and candle:
            one, p1 = market_klines(row["symbol"], "1", candle["open_time"], candle["open_time"]+5*60_000-1)
            ev1, c1, tp1_1 = event_from(one, g)
            if ev1 in {"SL","TP2"}: ev, candle = ev1, c1 or candle
            else: ev = "AMBIGUOUS"
            tp1_seen = tp1_seen or tp1_1; provider += "+1M:"+p1
        mfe, mae = excursions(candles, g)
        if ev == "SL": status,r,terminal,exit_ms="LOSS",-1.0,True,int(candle["open_time"] if candle else maturity)
        elif ev == "TP2": status,r,terminal,exit_ms="WIN_TP2",float(g["rr_tp2"]),True,int(candle["open_time"] if candle else maturity)
        elif ev == "AMBIGUOUS": status,r,terminal,exit_ms="AMBIGUOUS",None,False,None
        else:
            last=candles[-1]["close"]
            directional=(last-g["entry"]) if g["direction"]=="LONG" else (g["entry"]-last)
            r=directional/g["risk_abs"]; status="EXPIRED_TP1" if tp1_seen else "EXPIRED"; terminal=True; exit_ms=maturity
        return {"id":row["id"],"status":status,"terminal":terminal,"r_multiple":None if r is None else round(float(r),4),
                "exit_at_ms":exit_ms,"tp1_reached":bool(tp1_seen),"mfe_r":mfe,"mae_r":mae,"market_source":provider}
    except Exception as e:
        return {"id":row["id"],"status":"MARKET_DATA_ERROR","terminal":False,"r_multiple":None,"exit_at_ms":None,"error":str(e)[:700]}


def portfolio_report(manifest, cohort, settlements, generated_at, observed_through, checkpoints=None):
    checkpoints=checkpoints or {}
    by_id={s["id"]:s for s in settlements}; start=float(manifest["starting_equity_usd"]); equity=start; peak=start; max_dd=0.0
    closed=[]
    for row in cohort:
        s=by_id.get(row["id"],{}); r=fnum(s.get("r_multiple"))
        if not s.get("terminal") or r is None: continue
        pnl=round(float(row["risk_usd"])*r,2)
        closed.append({"row":row,"settlement":s,"pnl_usd":pnl})
    closed.sort(key=lambda x:(x["settlement"].get("exit_at_ms") or 10**30,x["row"]["captured_at_ms"]))
    equity_curve=[]
    for x in closed:
        equity=round(equity+x["pnl_usd"],2); peak=max(peak,equity)
        dd=(peak-equity)/peak*100 if peak else 0.0; max_dd=max(max_dd,dd)
        equity_curve.append({"trade_id":x["row"]["id"],"exit_at_ms":x["settlement"]["exit_at_ms"],"pnl_usd":x["pnl_usd"],"equity_usd":equity,"drawdown_pct":round(dd,4)})
    rs=[float(x["settlement"]["r_multiple"]) for x in closed]; wins=[x for x in closed if x["pnl_usd"]>0]; losses=[x for x in closed if x["pnl_usd"]<0]
    def direction_stats(direction):
        z=[x for x in closed if x["row"]["direction"]==direction]; p=sum(x["pnl_usd"] for x in z)
        return {"closed":len(z),"pnl_usd":round(p,2),"win_rate_pct":round(100*sum(x["pnl_usd"]>0 for x in z)/len(z),2) if z else None}
    checkpoint_summary={}
    for h in PRODUCT_CHECKPOINT_HOURS:
        vals=[]
        for rows in checkpoints.values():
            for cp in rows:
                if cp.get("checkpoint_h")==h and cp.get("matured") and fnum(cp.get("r_multiple")) is not None:
                    vals.append(float(cp["r_multiple"]))
        checkpoint_summary[f"{h}h"]={"matured":len(vals),"avg_r":round(sum(vals)/len(vals),4) if vals else None,
                                          "positive_pct":round(100*sum(v>0 for v in vals)/len(vals),2) if vals else None}
    detail=[]; eq_after={x["trade_id"]:x for x in equity_curve}
    for row in cohort:
        s=by_id.get(row["id"],{"status":"OPEN","terminal":False,"r_multiple":None}); e=eq_after.get(row["id"])
        detail.append({**row,"product_window_checkpoints":checkpoints.get(row["id"],[]),"settlement":s,
                       "pnl_usd":e["pnl_usd"] if e else None,"equity_after_usd":e["equity_usd"] if e else None,"drawdown_after_pct":e["drawdown_pct"] if e else None})
    return {
        "schema":SCHEMA,"generated_at":generated_at,"observed_through_at":observed_through.isoformat(),"manifest_hash":manifest["manifest_hash"],
        "product_horizon":PRODUCT_HORIZON,"evaluation_horizons":["4h","8h","12h"],
        "paper_only":True,"live_execution":False,"can_override_production":False,"production_threshold_unchanged":manifest["production_threshold"],
        "methodology":"Prospective canonical TRADE READY entries only; frozen Entry/SL/TP2; 4h/8h/12h product-window checkpoints; 5m first-touch with 1m ambiguity refinement; 12h terminal mark-to-market expiry; gross paper P&L before fees/slippage.",
        "cost_note":"Gross paper performance. Exchange fees, funding and slippage are not deducted and results must not be described as live-account P&L.",
        "checkpoint_summary":checkpoint_summary,
        "portfolio":{"starting_equity_usd":start,"equity_usd":round(equity,2),"net_pnl_usd":round(equity-start,2),"return_pct":round((equity/start-1)*100,4),
                     "peak_equity_usd":round(peak,2),"max_drawdown_pct":round(max_dd,4),"entries":len(cohort),"closed":len(closed),
                     "open_or_unresolved":len(cohort)-len(closed),"wins":len(wins),"losses":len(losses),
                     "win_rate_pct":round(100*len(wins)/len(closed),2) if closed else None,"net_r":round(sum(rs),4),"avg_r":round(sum(rs)/len(rs),4) if rs else None,
                     "long":direction_stats("LONG"),"short":direction_stats("SHORT")},
        "equity_curve":equity_curve,"trades":detail
    }


def main():
    manifest=load_manifest(); start=parse_time(manifest["cohort_start_at"]); snapshots=load_snapshots(start)
    cohort=load_jsonl(COHORT); previous_integrity=json.loads(INTEGRITY.read_text()) if INTEGRITY.exists() else None
    previous_report=json.loads(LATEST.read_text()) if LATEST.exists() else None
    verify_append_only(cohort, previous_integrity)
    cursor=previous_observed_through(manifest, previous_report); sizing_equity=previous_equity(manifest, previous_report)
    added,newest=enroll_new(manifest, cohort, snapshots, cursor, sizing_equity)
    now_ms=int(time.time()*1000); settlements=[]; checkpoints={}
    for i,row in enumerate(cohort):
        checkpoints[row["id"]]=[checkpoint_entry(row,h,now_ms) for h in PRODUCT_CHECKPOINT_HOURS]
        settlements.append(settle_entry(row,float(manifest["holding_horizon_hours"]),now_ms))
        if i and i%12==0: time.sleep(0.25)
    generated=dt.datetime.now(dt.timezone.utc).isoformat(); report=portfolio_report(manifest,cohort,settlements,generated,newest,checkpoints)
    COHORT.parent.mkdir(parents=True,exist_ok=True); COHORT.write_text("\n".join(canonical(r) for r in cohort)+("\n" if cohort else ""))
    LATEST.write_text(json.dumps(report,indent=2,sort_keys=True))
    hashes=verify_append_only(cohort, previous_integrity); chain=hashlib.sha256("".join(hashes).encode()).hexdigest()
    integrity={"schema":INTEGRITY_SCHEMA,"generated_at":generated,"manifest_hash":manifest["manifest_hash"],"append_only_verified":True,
               "row_count":len(cohort),"new_row_count":len(added),"row_hashes":hashes,"chain_sha256":chain,
               "paper_only":True,"live_execution":False,"can_override_production":False}
    INTEGRITY.write_text(json.dumps(integrity,indent=2,sort_keys=True))
    print(json.dumps({"schema":SCHEMA,"added":len(added),"integrity":integrity,"portfolio":report["portfolio"],"checkpoint_summary":report["checkpoint_summary"]},indent=2))


if __name__ == "__main__": main()
