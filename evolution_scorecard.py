from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Iterable

SCHEMA = "ATLAS_EVOLUTION_SCORECARD_V1"
BASELINE = {
    "captured_at": "2026-09-12T05:10:55Z",
    "entries": 3,
    "wins": 2,
    "losses": 1,
    "win_rate_pct": 66.67,
    "net_r": 1.5592,
    "avg_r": 0.5197,
    "profit_factor": 2.5336,
    "max_drawdown_pct": 1.0,
    "return_pct": 1.5336,
}


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def _trade_id(row: dict[str, Any]) -> str:
    return str(row.get("decision_id") or row.get("id") or "")


def validate_canonical_trades(trades: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(trades)
    ids = [_trade_id(r) for r in rows]
    assert all(ids), "canonical trade missing decision_id"
    assert len(ids) == len(set(ids)), "duplicate canonical decision_id"
    for row in rows:
        assert row.get("decision_action") == "TRADE_READY", "non-TRADE_READY row entered canonical KPI"
        assert row.get("decision_source") == "FINAL_TRADE_GATE", "non-final-gate row entered canonical KPI"
        assert row.get("paper_only") is True
        assert row.get("live_execution") is False
        assert row.get("product_horizon") == "4-12H"
    return rows


def _r(row: dict[str, Any]) -> float | None:
    settlement = row.get("settlement") or {}
    value = settlement.get("r_multiple")
    return None if value is None else float(value)


def _direction_metrics(rows: list[dict[str, Any]], direction: str) -> dict[str, Any]:
    selected = [r for r in rows if r.get("direction") == direction]
    terminal = [r for r in selected if (r.get("settlement") or {}).get("terminal") is True and _r(r) is not None]
    rs = [_r(r) for r in terminal]
    positive = [x for x in rs if x is not None and x > 0]
    negative = [x for x in rs if x is not None and x < 0]
    gross_win = sum(positive)
    gross_loss = abs(sum(negative))
    return {
        "entries": len(selected),
        "resolved": len(terminal),
        "open_or_unresolved": len(selected) - len(terminal),
        "wins": len(positive),
        "losses": len(negative),
        "win_rate_pct": round((len(positive) / len(terminal) * 100), 2) if terminal else None,
        "net_r": round(sum(x for x in rs if x is not None), 4),
        "avg_r": round(sum(x for x in rs if x is not None) / len(rs), 4) if rs else None,
        "median_r": round(median(rs), 4) if rs else None,
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss > 0 else (None if not positive else "INF"),
    }


def _sample_label(n: int) -> str:
    if n < 10:
        return "EARLY_INSUFFICIENT_SAMPLE"
    if n < 20:
        return "EARLY_SAMPLE"
    if n < 30:
        return "DEVELOPING_SAMPLE"
    return "MEANINGFUL_FORWARD_SAMPLE"


def _delta(current: float | int | None, baseline: float | int | None) -> float | None:
    if current is None or baseline is None:
        return None
    return round(float(current) - float(baseline), 4)


def _canonical_forward_counts(payload: dict[str, Any]) -> tuple[Any, Any]:
    summary = payload.get("summary") or {}
    trade_ready = payload.get("forward_trade_ready_count")
    wait_directional = payload.get("forward_wait_directional_count")
    if trade_ready is None:
        trade_ready = summary.get("forward_trade_ready_count")
    if wait_directional is None:
        wait_directional = summary.get("forward_wait_directional_count")
    return trade_ready, wait_directional


def build_scorecard(
    portfolio: dict[str, Any],
    canonical_outcomes: dict[str, Any] | None = None,
    analyst_forward: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert portfolio.get("schema") == "ATLAS_PAPER_PORTFOLIO_10K_V3_CANONICAL_TRUTH"
    assert portfolio.get("decision_source_of_truth") == "FINAL_TRADE_GATE"
    assert portfolio.get("paper_only") is True
    assert portfolio.get("live_execution") is False
    assert portfolio.get("production_threshold_unchanged") == 68

    trades = validate_canonical_trades(portfolio.get("trades") or [])
    p = portfolio.get("portfolio") or {}
    assert p.get("entries") == len(trades), "portfolio entry count diverges from canonical trade rows"

    status_counts = Counter((r.get("settlement") or {}).get("status") or "OPEN" for r in trades)
    current = {
        "entries": p.get("entries"),
        "closed": p.get("closed"),
        "wins": p.get("wins"),
        "losses": p.get("losses"),
        "open_or_unresolved": p.get("open_or_unresolved"),
        "win_rate_pct": p.get("win_rate_pct"),
        "net_r": p.get("net_r"),
        "avg_r": p.get("avg_r"),
        "profit_factor": p.get("profit_factor"),
        "max_drawdown_pct": p.get("max_drawdown_pct"),
        "return_pct": p.get("return_pct"),
        "equity_usd": p.get("equity_usd"),
        "starting_equity_usd": p.get("starting_equity_usd"),
        "sample_status": _sample_label(int(p.get("entries") or 0)),
        "settlement_status_counts": dict(sorted(status_counts.items())),
    }

    comparison = {
        "entries_delta": _delta(current["entries"], BASELINE["entries"]),
        "win_rate_pct_delta": _delta(current["win_rate_pct"], BASELINE["win_rate_pct"]),
        "net_r_delta": _delta(current["net_r"], BASELINE["net_r"]),
        "avg_r_delta": _delta(current["avg_r"], BASELINE["avg_r"]),
        "profit_factor_delta": _delta(current["profit_factor"], BASELINE["profit_factor"]),
        "max_drawdown_pct_delta": _delta(current["max_drawdown_pct"], BASELINE["max_drawdown_pct"]),
        "return_pct_delta": _delta(current["return_pct"], BASELINE["return_pct"]),
        "claim_allowed": int(current["entries"] or 0) >= 10,
        "verdict": "EARLY / INSUFFICIENT SAMPLE" if int(current["entries"] or 0) < 10 else "REQUIRES_MULTI_METRIC_REVIEW",
        "rule": "Never call improvement from win rate alone; require forward sample growth and improvement across expectancy/net R, profit factor and drawdown context.",
    }

    evidence = {
        "canonical_forward": {
            "role": "OFFICIAL_FORWARD_KPI",
            "source": "status/paper-portfolio-10k-latest.json",
            "may_override_kpi": True,
        },
        "historical_counterfactual": {
            "role": "RESEARCH_ONLY_NOT_FORWARD_PROOF",
            "may_override_kpi": False,
        },
        "shadow": {
            "role": "SHADOW_ONLY",
            "may_override_kpi": False,
        },
    }
    if canonical_outcomes:
        forward_trade_ready_count, forward_wait_directional_count = _canonical_forward_counts(canonical_outcomes)
        evidence["canonical_outcomes"] = {
            "role": "SUPPORTING_FORWARD_EVIDENCE",
            "forward_trade_ready_count": forward_trade_ready_count,
            "forward_wait_directional_count": forward_wait_directional_count,
            "note": "Counts are not merged into official $10k KPI unless present as canonical portfolio entries.",
        }
    if analyst_forward:
        evidence["analyst_forward_attribution"] = {
            "role": "DIAGNOSTIC_ONLY",
            "analysis_only": analyst_forward.get("analysis_only", True),
            "may_override_kpi": False,
        }

    return {
        "schema": SCHEMA,
        "product_lane": "CORE_4_12H",
        "product_horizon": "4-12H",
        "decision_source_of_truth": "FINAL_TRADE_GATE",
        "production_threshold_unchanged": 68,
        "paper_only": True,
        "live_execution": False,
        "cost_basis": "GROSS_PAPER_BEFORE_FEES_FUNDING_SLIPPAGE",
        "cost_note": portfolio.get("cost_note"),
        "baseline_frozen": dict(BASELINE),
        "canonical_forward_performance": current,
        "comparison_to_baseline": comparison,
        "direction_cohorts": {
            "LONG": _direction_metrics(trades, "LONG"),
            "SHORT": _direction_metrics(trades, "SHORT"),
        },
        "evidence_lanes": evidence,
        "integrity": {
            "unique_decision_ids": True,
            "canonical_rows": len(trades),
            "direction_entries_sum": sum(_direction_metrics(trades, d)["entries"] for d in ("LONG", "SHORT")),
            "historical_or_shadow_in_official_kpi": False,
        },
    }


def main() -> None:
    portfolio = _load("status/paper-portfolio-10k-latest.json")
    canonical_path = Path("status/canonical-outcomes-latest.json")
    analyst_path = Path("status/analyst-forward-attribution-latest.json")
    report = build_scorecard(
        portfolio,
        _load(canonical_path) if canonical_path.exists() else None,
        _load(analyst_path) if analyst_path.exists() else None,
    )
    assert report["integrity"]["direction_entries_sum"] == report["canonical_forward_performance"]["entries"]
    out = Path("status/atlas-evolution-scorecard-latest.json")
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"schema": SCHEMA, "entries": report["canonical_forward_performance"]["entries"], "verdict": report["comparison_to_baseline"]["verdict"]}))


if __name__ == "__main__":
    main()
