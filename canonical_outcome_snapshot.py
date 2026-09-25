#!/usr/bin/env python3
"""Build and load the web-safe canonical ATLAS outcome snapshot.

The snapshot is derived only from the prospective canonical $10K paper portfolio
and canonical offline forward evaluation. Legacy score-qualified path research is
intentionally excluded and never backfilled into official Production outcomes.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

VERSION = "ATLAS_CANONICAL_OUTCOME_SNAPSHOT_V3_STRICT_EXECUTION_ELIGIBILITY"
SOURCE = "FINAL_TRADE_GATE"
HORIZONS = [4, 8, 12]
PAPER_SCHEMA = "ATLAS_PAPER_PORTFOLIO_10K_V3_CANONICAL_TRUTH"
FORWARD_SCHEMA = "ATLAS_OFFLINE_FORWARD_EVALUATION_V4_CANONICAL_TRUTH"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _trade_rows(paper: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in paper.get("trades") or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        source = row.get("decision_source") or row.get("decision_source_of_truth")
        decision_id = row.get("decision_id") or row.get("id")
        direction = str(row.get("direction") or "").upper()
        if source != SOURCE or not decision_id or direction not in {"LONG", "SHORT"}:
            continue
        # A Final-Gate label alone is not sufficient for executable-performance
        # accounting.  If capture-time execution eligibility is explicitly false,
        # preserve the row in research upstream but exclude it from the official
        # executable cohort.  Missing legacy fields remain accepted for backward
        # compatibility with the canonical paper ledger.
        if row.get("execution_ready_at_capture") is not True:
            continue
        row["decision_id"] = str(decision_id)
        row["decision_source_of_truth"] = SOURCE
        row["evaluation_horizons_h"] = HORIZONS
        row["legacy_backfill_allowed"] = False
        rows.append(row)
    return rows


def build(root: Path) -> dict[str, Any]:
    paper = _read(root / "status/paper-portfolio-10k-latest.json")
    forward = _read(root / "status/offline-forward-evaluation-latest.json")
    if paper.get("schema") != PAPER_SCHEMA:
        raise RuntimeError(f"unexpected paper schema: {paper.get('schema')}")
    if paper.get("decision_source_of_truth") != SOURCE:
        raise RuntimeError("paper portfolio is not FINAL_TRADE_GATE canonical")
    if list(paper.get("evaluation_horizons") or []) != ["4h", "8h", "12h"]:
        raise RuntimeError("paper portfolio horizons are not 4/8/12")
    if forward.get("schema") != FORWARD_SCHEMA:
        raise RuntimeError(f"unexpected forward schema: {forward.get('schema')}")
    if forward.get("decision_source_of_truth") != SOURCE:
        raise RuntimeError("forward evaluation is not FINAL_TRADE_GATE canonical")
    if list(forward.get("evaluation_horizons_h") or []) != HORIZONS:
        raise RuntimeError("forward evaluation horizons are not 4/8/12")
    if forward.get("legacy_backfill_performed") is not False:
        raise RuntimeError("canonical forward report permits legacy backfill")

    trades = _trade_rows(paper)
    portfolio = dict(paper.get("portfolio") or {})
    checkpoints = dict(paper.get("checkpoint_summary") or {})
    forward_trade_ready = int(forward.get("trade_ready_count") or 0)
    forward_wait = int(forward.get("wait_directional_count") or 0)
    geometry_rows = sum(1 for x in trades if isinstance(x.get("geometry"), dict))
 
    # Portfolio aggregates in the source paper ledger may include legacy rows
    # that were deliberately excluded above. Never expose those aggregates as
    # official executable performance for the strict cohort.
    strict_portfolio = {
        "entries": len(trades),
        "closed": 0,
        "open_or_unresolved": len(trades),
        "wins": 0,
        "losses": 0,
        "win_rate_pct": None,
        "avg_r": None,
        "net_r": None,
        "profit_factor": None,
        "max_drawdown_pct": None,
    }
    if trades:
        settled = [r for r in trades if isinstance(r.get("r_multiple"), (int, float))]
        rs = [float(r["r_multiple"]) for r in settled]
        wins_n = sum(1 for x in rs if x > 0)
        losses_n = sum(1 for x in rs if x < 0)
        gross_win = sum(x for x in rs if x > 0)
        gross_loss = abs(sum(x for x in rs if x < 0))
        strict_portfolio.update({
            "closed": len(settled),
            "open_or_unresolved": len(trades) - len(settled),
            "wins": wins_n,
            "losses": losses_n,
            "win_rate_pct": round(100.0 * wins_n / len(settled), 2) if settled else None,
            "avg_r": round(sum(rs) / len(rs), 4) if rs else None,
            "net_r": round(sum(rs), 4) if rs else None,
            "profit_factor": round(gross_win / gross_loss, 4) if gross_loss > 0 else (None if not rs else float("inf")),
        })

    return {
        "schema": VERSION,
        "generated_at": _iso_now(),
        "decision_source_of_truth": SOURCE,
        "product_horizon": "4-12H",
        "evaluation_horizons_h": HORIZONS,
        "legacy_backfill_allowed": False,
        "legacy_score_path_research_included": False,
        "official_trade_authority": "PAPER_PORTFOLIO_CANONICAL_FINAL_GATE_EXECUTION_ELIGIBLE_ENTRIES",
        "execution_eligibility_policy": "REQUIRE_EXPLICIT_EXECUTION_READY_TRUE",
        "signals": {
            "count": len(trades),
            "rows": trades,
        },
        "summary": {
            "portfolio": strict_portfolio,
            "checkpoint_summary": checkpoints,
            "forward_trade_ready_count": forward_trade_ready,
            "forward_wait_directional_count": forward_wait,
        },
        "path_summary": {
            **strict_portfolio,
        },
        "geometry_status": {
            "canonical_trade_rows": len(trades),
            "rows_with_frozen_geometry": geometry_rows,
            "coverage_pct": round(100.0 * geometry_rows / len(trades), 2) if trades else None,
            "source": SOURCE,
        },
        "settlement_status": {
            "observed_through_at": paper.get("observed_through_at"),
            "paper_generated_at": paper.get("generated_at"),
            "forward_generated_at": forward.get("generated_at"),
            "web_process_background_worker": False,
            "outcome_read_triggered_by_request": False,
        },
        "safety": {
            "research_only": True,
            "paper_only": True,
            "live_execution": False,
            "can_override_production": False,
            "production_threshold_unchanged": paper.get("production_threshold_unchanged"),
        },
    }


def validate(payload: dict[str, Any]) -> None:
    if payload.get("schema") != VERSION:
        raise RuntimeError("canonical outcome snapshot schema mismatch")
    if payload.get("decision_source_of_truth") != SOURCE:
        raise RuntimeError("canonical outcome snapshot source mismatch")
    if list(payload.get("evaluation_horizons_h") or []) != HORIZONS:
        raise RuntimeError("canonical outcome snapshot horizon mismatch")
    if payload.get("legacy_backfill_allowed") is not False:
        raise RuntimeError("legacy backfill is not allowed")
    rows = ((payload.get("signals") or {}).get("rows") or [])
    path = payload.get("path_summary") or {}
    if int(path.get("entries") or 0) != len(rows):
        raise RuntimeError("strict outcome summary does not match eligible rows")
    if not rows and any(path.get(k) not in (None, 0) for k in ("closed", "wins", "losses", "net_r", "avg_r", "profit_factor", "max_drawdown_pct")):
        raise RuntimeError("legacy performance leaked into empty strict cohort")
    for row in ((payload.get("signals") or {}).get("rows") or []):
        if row.get("decision_source_of_truth") != SOURCE or not row.get("decision_id"):
            raise RuntimeError("noncanonical trade row in outcome snapshot")
        if list(row.get("evaluation_horizons_h") or []) != HORIZONS:
            raise RuntimeError("trade row horizon mismatch")


def load_snapshot(root: Path) -> dict[str, Any]:
    path = root / "status/canonical-outcomes-latest.json"
    try:
        payload = _read(path)
        validate(payload)
        return payload
    except Exception as exc:
        return {
            "schema": VERSION,
            "state": "DATA_UNAVAILABLE",
            "error": f"{type(exc).__name__}: {exc}",
            "decision_source_of_truth": SOURCE,
            "product_horizon": "4-12H",
            "evaluation_horizons_h": HORIZONS,
            "legacy_backfill_allowed": False,
            "signals": {"count": 0, "rows": []},
            "summary": {},
            "path_summary": {},
            "geometry_status": {"canonical_trade_rows": 0, "rows_with_frozen_geometry": 0, "coverage_pct": None, "source": SOURCE},
            "settlement_status": {"web_process_background_worker": False, "outcome_read_triggered_by_request": False},
            "safety": {"research_only": True, "paper_only": True, "live_execution": False, "can_override_production": False},
        }


def main() -> int:
    root = Path(__file__).resolve().parent
    payload = build(root)
    validate(payload)
    out = root / "status/canonical-outcomes-latest.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "schema": VERSION, "signals": payload["signals"]["count"], "out": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
