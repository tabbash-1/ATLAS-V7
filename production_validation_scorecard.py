#!/usr/bin/env python3
"""ATLAS post-V2 Production validation scorecard.

Descriptive evidence only. Reads the committed canonical FINAL_TRADE_GATE outcome
snapshot, isolates the post-HTF/SR-V2 epoch, and reports true candle-path paper
settlements. It cannot change Production, thresholds, risk, or execution.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from typing import Any

VERSION = "ATLAS_PRODUCTION_VALIDATION_SCORECARD_V1"
SOURCE = "FINAL_TRADE_GATE"
EPOCH_ID = "HTF_SR_V2_2026-09-14"
EPOCH_START = dt.datetime(2026, 9, 14, 12, 31, 29, tzinfo=dt.timezone.utc)
MIN_FORMAL_SAMPLE = 30


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ts(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        x = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def _pf(rs: list[float]):
    pos = sum(x for x in rs if x > 0)
    neg = abs(sum(x for x in rs if x < 0))
    if neg > 0:
        return round(pos / neg, 4)
    return "INF" if pos > 0 else None


def _max_dd_pct(rows: list[dict[str, Any]]) -> float | None:
    values = [float(x["equity_after_usd"]) for x in rows if x.get("equity_after_usd") is not None]
    if not values:
        return None
    peak = 10000.0
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, 100.0 * (peak - value) / peak)
    return round(worst, 4)


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    terminal = [x for x in rows if (x.get("settlement") or {}).get("terminal") is True]
    rs = [float((x.get("settlement") or {}).get("r_multiple")) for x in terminal if (x.get("settlement") or {}).get("r_multiple") is not None]
    positive = [x for x in terminal if float((x.get("settlement") or {}).get("r_multiple") or 0) > 0]
    negative = [x for x in terminal if float((x.get("settlement") or {}).get("r_multiple") or 0) < 0]
    flat = [x for x in terminal if float((x.get("settlement") or {}).get("r_multiple") or 0) == 0]
    tp2 = [x for x in terminal if (x.get("settlement") or {}).get("status") == "WIN_TP2"]
    tp1 = [x for x in terminal if (x.get("settlement") or {}).get("tp1_reached")]
    pnl = sum(float(x.get("pnl_usd") or 0) for x in terminal)
    by_direction = {}
    for direction in ("LONG", "SHORT"):
        part = [x for x in terminal if str(x.get("direction") or "").upper() == direction]
        prs = [float((x.get("settlement") or {}).get("r_multiple")) for x in part if (x.get("settlement") or {}).get("r_multiple") is not None]
        by_direction[direction.lower()] = {
            "n": len(part), "net_r": round(sum(prs), 4) if prs else None,
            "positive_pct": round(100 * sum(1 for r in prs if r > 0) / len(prs), 2) if prs else None,
        }
    return {
        "entries": len(rows), "terminal": len(terminal), "open_or_unresolved": len(rows) - len(terminal),
        "positive": len(positive), "negative": len(negative), "flat": len(flat),
        "positive_rate_pct": round(100 * len(positive) / len(terminal), 2) if terminal else None,
        "tp2_wins": len(tp2), "tp1_reached": len(tp1),
        "net_r": round(sum(rs), 4) if rs else None,
        "avg_r": round(sum(rs) / len(rs), 4) if rs else None,
        "profit_factor_r": _pf(rs), "paper_pnl_usd": round(pnl, 2),
        "max_drawdown_pct": _max_dd_pct(terminal), "by_direction": by_direction,
    }


def build(root: Path) -> dict[str, Any]:
    source = _read(root / "status/canonical-outcomes-latest.json")
    if source.get("decision_source_of_truth") != SOURCE:
        raise RuntimeError("canonical outcome source is not FINAL_TRADE_GATE")
    if source.get("legacy_backfill_allowed") is not False:
        raise RuntimeError("legacy backfill must remain disabled")
    all_rows = list(((source.get("signals") or {}).get("rows") or []))
    post = []
    for row in all_rows:
        captured = _ts(row.get("captured_at"))
        if captured and captured >= EPOCH_START and row.get("decision_source_of_truth") == SOURCE:
            post.append(dict(row))
    post.sort(key=lambda x: int(x.get("captured_at_ms") or 0))
    summary = _summarize(post)
    n = summary["terminal"]
    formal_ready = n >= MIN_FORMAL_SAMPLE
    state = "FORMAL_SAMPLE_READY" if formal_ready else "COLLECTING_FORWARD_EVIDENCE"
    return {
        "schema": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "epoch": {"id": EPOCH_ID, "start": EPOCH_START.isoformat(), "legacy_rows_excluded": len(all_rows) - len(post)},
        "decision_source_of_truth": SOURCE, "product_horizon": "4-12H",
        "settlement_semantics": "CANONICAL_CANDLE_PATH_PAPER_SETTLEMENT",
        "state": state,
        "sample_readiness": {"formal_min_terminal": MIN_FORMAL_SAMPLE, "terminal": n, "ready": formal_ready, "remaining": max(0, MIN_FORMAL_SAMPLE - n)},
        "post_v2": summary,
        "rows": post,
        "interpretation": {
            "profitability_claim_allowed": False,
            "reason": "FORWARD_SAMPLE_BELOW_FORMAL_MINIMUM" if not formal_ready else "FORMAL_REVIEW_REQUIRED",
            "automatic_strategy_change": False,
        },
        "safety": {"paper_only": True, "research_only": True, "live_execution": False, "can_override_production": False, "can_change_threshold": False, "production_threshold": 68},
    }


def validate(p: dict[str, Any]) -> None:
    assert p.get("schema") == VERSION
    assert p.get("decision_source_of_truth") == SOURCE
    assert p.get("epoch", {}).get("id") == EPOCH_ID
    assert p.get("safety", {}).get("production_threshold") == 68
    assert p.get("safety", {}).get("can_override_production") is False
    assert p.get("interpretation", {}).get("profitability_claim_allowed") is False
    for row in p.get("rows") or []:
        assert _ts(row.get("captured_at")) >= EPOCH_START
        assert row.get("decision_source_of_truth") == SOURCE


def load_scorecard(root: Path) -> dict[str, Any]:
    try:
        p = _read(root / "status/production-validation-latest.json")
        validate(p)
        return p
    except Exception as exc:
        return {"schema": VERSION, "state": "DATA_UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}", "safety": {"live_execution": False, "can_override_production": False}}


def main() -> int:
    root = Path(__file__).resolve().parent
    p = build(root); validate(p)
    out = root / "status/production-validation-latest.json"
    out.write_text(json.dumps(p, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "state": p["state"], "terminal": p["post_v2"]["terminal"], "net_r": p["post_v2"]["net_r"], "out": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
