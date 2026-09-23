"""Evidence-only family validation for ATLAS Trade Edge V1.

Consumes settled canonical Production geometry. No Production authority.
The purpose is to prevent directional-return evidence from being mistaken for
realized trade-path edge.
"""
from __future__ import annotations

VERSION = "ATLAS_TRADE_EDGE_FAMILY_VALIDATION_V1"
MIN_FAMILY_N = 10


def _f(v):
    try: return float(v)
    except Exception: return None


def summarize(records):
    groups = {}
    for row in records or []:
        g = row.get("geometry") or {}
        direction = str(g.get("direction") or "").upper()
        regime = str(row.get("regime") or "").upper()
        playbook = str(row.get("playbook") or "").upper()
        r = _f(row.get("r_multiple"))
        if not row.get("terminal") or r is None or direction not in {"LONG","SHORT"}:
            continue
        groups.setdefault((direction,regime,playbook), []).append(row)

    out = []
    for key, rows in sorted(groups.items()):
        rs = [_f(x.get("r_multiple")) for x in rows]
        net = sum(rs)
        wins = sum(1 for r in rs if r > 0)
        mfe = [_f(x.get("mfe_r")) for x in rows if _f(x.get("mfe_r")) is not None]
        mae = [_f(x.get("mae_r")) for x in rows if _f(x.get("mae_r")) is not None]
        n = len(rs)
        avg = net/n
        status = "INSUFFICIENT_SAMPLE"
        if n >= MIN_FAMILY_N:
            status = "HISTORICAL_POSITIVE_EDGE" if avg > 0 else "HISTORICAL_NEGATIVE_EDGE"
        out.append({
            "direction":key[0],"regime":key[1],"playbook":key[2],"n":n,
            "net_r":round(net,4),"avg_r":round(avg,4),
            "win_rate_pct":round(100*wins/n,2),
            "avg_mfe_r":round(sum(mfe)/len(mfe),4) if mfe else None,
            "avg_mae_r":round(sum(mae)/len(mae),4) if mae else None,
            "evidence_status":status,
            "can_override_production":False,
        })
    return {
        "version":VERSION,
        "minimum_family_sample":MIN_FAMILY_N,
        "families":out,
        "proof_semantics":"HISTORICAL_FROZEN_ENTRY_SL_TP_PATH_EVIDENCE_NOT_PROSPECTIVE_PROOF",
        "promotion_requirement":"PROSPECTIVE_POST_BASELINE_OUT_OF_SAMPLE_POSITIVE_EV",
        "can_override_production":False,
        "live_execution":False,
    }
