"""Prospective evidence pipeline for ATLAS Trade Edge.

Freezes a baseline timestamp/commit, evaluates only later settled episodes, and
separates historical discovery from prospective proof. Evidence-only: it cannot
change Production, thresholds, FINAL_TRADE_GATE, alerts, or execution.
"""
from __future__ import annotations
import datetime as dt

VERSION="ATLAS_TRADE_EDGE_PROSPECTIVE_V2_POST_FIX_COHORT"
MIN_PROOF_N=20
MIN_FAMILY_N=8
MIN_AVG_R=0.10
MIN_PROFIT_FACTOR=1.20

def _t(v):
    return dt.datetime.fromisoformat(str(v).replace("Z","+00:00"))

def _f(v):
    try:return float(v)
    except Exception:return None

def _summary(rows):
    rs=[_f(x.get("r_multiple")) for x in rows]
    rs=[x for x in rs if x is not None]
    wins=[x for x in rs if x>0]; losses=[x for x in rs if x<0]
    pos=sum(wins); neg=abs(sum(losses))
    return {
      "n":len(rs),"net_r":round(sum(rs),4),
      "avg_r":round(sum(rs)/len(rs),4) if rs else None,
      "win_rate_pct":round(100*len(wins)/len(rs),2) if rs else None,
      "profit_factor_r":round(pos/neg,4) if neg else None,
    }

def evaluate(records, baseline_at, baseline_commit):
    base=_t(baseline_at)
    post=[]
    for x in records or []:
        try: captured=_t(x.get("captured_at"))
        except Exception: continue
        if captured <= base or not x.get("terminal") or _f(x.get("r_multiple")) is None:
            continue
        post.append(x)

    groups={}
    for x in post:
        g=x.get("geometry") or {}
        key=(str(g.get("direction") or "").upper(),str(x.get("regime") or "").upper(),str(x.get("playbook") or "").upper())
        groups.setdefault(key,[]).append(x)

    families=[]
    for key,rows in sorted(groups.items()):
        s=_summary(rows)
        enough=s["n"]>=MIN_FAMILY_N
        positive=bool(enough and s["avg_r"] is not None and s["avg_r"]>=MIN_AVG_R and
                      s["profit_factor_r"] is not None and s["profit_factor_r"]>=MIN_PROFIT_FACTOR)
        families.append({**s,"direction":key[0],"regime":key[1],"playbook":key[2],
          "prospective_status":"PROSPECTIVE_POSITIVE" if positive else ("PROSPECTIVE_NEGATIVE_OR_WEAK" if enough else "COLLECTING"),
          "can_override_production":False})

    overall=_summary(post)
    proof=bool(overall["n"]>=MIN_PROOF_N and overall["avg_r"] is not None and overall["avg_r"]>=MIN_AVG_R and
               overall["profit_factor_r"] is not None and overall["profit_factor_r"]>=MIN_PROFIT_FACTOR)
    return {
      "version":VERSION,"baseline_at":baseline_at,"baseline_commit":baseline_commit,
      "cohort_policy":"STRICTLY_AFTER_FIX_BASELINE",
      "overall":overall,"families":families,
      "proof_status":"PROSPECTIVE_EDGE_PROVEN" if proof else "COLLECTING_OR_NOT_PROVEN",
      "proof_rules":{"min_n":MIN_PROOF_N,"min_family_n":MIN_FAMILY_N,"min_avg_r":MIN_AVG_R,"min_profit_factor_r":MIN_PROFIT_FACTOR},
      "historical_rows_excluded":True,"can_override_production":False,"live_execution":False,
    }
