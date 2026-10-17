#!/usr/bin/env python3
"""ATLAS Edge 90-day real-market regime audit, research only.

Predeclared *descriptive* stratification of four fixed baseline rules:
BTC's completed 12h direction, each policy's LONG/SHORT, asset/BTC
directional agreement, ATR extension, and volatility. Do not optimize
filters/thresholds on these rows, or treat them as independent trades.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research.edge_event_ledger_v1 import HORIZON_H, HOUR_MS, build_ledger
from research.edge_real_market_baselines_v1 import (
    POLICIES, RESEARCH_UNIVERSE, _policy_direction, asof_last_closed_hour,
    fetch_completed_1h,
)

SCHEMA = "ATLAS_EDGE_90D_REAL_MARKET_REGIME_AUDIT_V1"
BENCHMARK_COST_BPS = 17.0
PREFROZEN_DAYS = 90
SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "DOGEUSDT", "ZECUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT",
    "LTCUSDT",
)
MIN_DAYS = 60
PURGE_H = 24  # 12h label + 12h embargo


def _stats(rows):
    vals = [r["settlement"]["modeled_net_r"] for r in rows
            if r["settlement"]["modeled_net_r"] is not None]
    gross = [r["settlement"]["gross_r"] for r in rows
             if r["settlement"]["gross_r"] is not None]
    # Unexecutable and same-hour double touch can *never* become winners
    positive = [x for x in vals if x > 0]
    negative = [x for x in vals if x < 0]
    return {
        "decisions": len(rows), "valid_settlements": len(vals),
        "excluded_ambiguous_or_gap": len(rows) - len(vals),
        "positive": len(positive), "negative": len(negative),
        "mean_gross_r": round(sum(gross) / len(gross), 5) if gross else None,
        "mean_modeled_net_r": round(sum(vals) / len(vals), 5) if vals else None,
        "sum_modeled_net_r_nonexecuted": round(sum(vals), 5) if vals else None,
        "modeled_net_positive_pct": round(100 * len(positive) / len(vals), 2) if vals else None,
        "modeled_net_profit_factor": round(sum(positive) / abs(sum(negative)), 4)
            if negative and positive else (0 if negative else None),
        "capital_deployment_and_position_overlap_not_modeled": True,
    }


def _btc_regime(f):
    # Frozen BTC previous 12h return; zero treated as directionless.
    ret = f["btc_return_12h_pct"]
    return "BTC_UP" if ret > 0 else "BTC_DOWN" if ret < 0 else "BTC_FLAT"


def _extension_regime(f):
    # Frozen signed distance from historical 20h mean in ATR units.
    ext = f.get("extension_atr_from_20h_mean")
    if ext is None:
        return "UNKNOWN"
    return "EXTENDED" if abs(ext) >= 1 else "NORMAL"


def _volatility_regime(f):
    # Fixed natural percentage boundary, deliberately not data-tuned.
    atr_pct = f["atr_pct"]
    return "ATR_GE_1PCT" if atr_pct >= 1 else "ATR_LT_1PCT"


def summarize(ledgers, train_pct=70):
    """Use one common chronological split and embargo, never select winner.

    Returns *descriptive* fixed-policy aggregates, including stratifications.
    The same market time for multiple symbols remains one correlated cluster.
    """
    if not 50 <= train_pct <= 80:
        raise ValueError("Invalid discovery split")
    seen = {}
    for ledger in ledgers:
        if ledger.get("schema") != "ATLAS_EDGE_EVENT_LEDGER_V1":
            raise ValueError("Unrecognized event labeling contract")
        for row in ledger["rows"]:
            key = (row["symbol"], row["event_at_ms"], row["direction"])
            if key in seen:
                raise ValueError("Repeated frozen observation")
            if row["forward_matures_at_ms"] <= row["event_at_ms"]:
                raise ValueError("Maturity precedes observation")
            seen[key] = row
    pairs = defaultdict(dict)
    for (symbol, ts, direction), row in seen.items():
        pairs[(symbol, ts)][direction] = row
    times = sorted({ts for (_, ts) in pairs})
    if len(times) < 30:
        raise ValueError("Insufficient independent observation timestamps")
    cutoff = times[int(len(times) * train_pct / 100)]
    buckets = {part: {name: defaultdict(list) for name in POLICIES}
               for part in ("discovery", "holdout")}
    purge_count = 0
    inconsistent = 0
    for (symbol, ts), by_side in sorted(pairs.items()):
        if set(by_side) != {"LONG", "SHORT"}:
            inconsistent += 1
            continue
        left = by_side["LONG"]
        right = by_side["SHORT"]
        if left["features"] != right["features"]:
            raise ValueError("LONG/SHORT observations not frozen against same evidence")
        if left["forward_matures_at_ms"] < cutoff - PURGE_H * HOUR_MS:
            section = "discovery"
        elif ts >= cutoff:
            section = "holdout"
        else:
            purge_count += 1
            continue
        f = left["features"]
        for policy in POLICIES:
            direction = _policy_direction(policy, f)
            if not direction:
                continue
            chosen = by_side[direction]
            lane = buckets[section][policy]
            lane["ALL"].append(chosen)
            lane[_btc_regime(f)].append(chosen)
            lane["SIDE_" + direction].append(chosen)
            lane["BTC_" + _extension_regime(f)].append(chosen)
            lane[_volatility_regime(f)].append(chosen)
            lane["ASSET_" + symbol].append(chosen)
    return {
        "split": {
            "discovery_percent": train_pct,
            "cutoff_ms": cutoff,
            "cutoff_utc": datetime.fromtimestamp(cutoff / 1000, timezone.utc).isoformat(),
            "purge_hours_before_holdout": PURGE_H,
            "purged_asset_time_events": purge_count,
            "inconsistent_pairs_excluded": inconsistent,
            "same_calendar_hours_across_symbols_are_correlated": True,
            "overlapping_12h_labels_from_4h_events_are_dependent": True,
        },
        "by_segment": {
            part: {p: {segment: _stats(rows) for segment, rows in groups.items()}
                   for p, groups in models.items()}
            for part, models in buckets.items()
        },
        "winner_selected": False,
        "model_fitted": False,
        "strategies_tuned_from_outcomes": False,
    }


def build_market_audit(symbols=SYMBOLS, days=PREFROZEN_DAYS,
                       as_of_ms=None, modeled_cost_bps=BENCHMARK_COST_BPS,
                       fetcher=fetch_completed_1h):
    if not MIN_DAYS <= days <= 180:
        raise ValueError("Use 60-180 calendar days")
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Duplicate or missing symbols")
    if len(symbols) > len(RESEARCH_UNIVERSE) or any(s not in RESEARCH_UNIVERSE for s in symbols):
        raise ValueError("Unsupported research universe")
    if modeled_cost_bps is None or not 0 <= modeled_cost_bps <= 100:
        raise ValueError("Provide an explicit 0-100 bps hypothetical cost")
    as_of_ms = asof_last_closed_hour(int(time.time() * 1000)) if as_of_ms is None else as_of_ms
    btc, btc_meta = fetcher("BTCUSDT", days, as_of_ms)
    if not btc_meta["continuity_validated"] or len(btc) != days * 24:
        raise ValueError("Unverified BTC market history")
    ledgers = []
    quality = [btc_meta]
    for symbol in symbols:
        if symbol == "BTCUSDT":
            market = btc
        else:
            market, meta = fetcher(symbol, days, as_of_ms)
            if not meta["continuity_validated"] or len(market) != days * 24:
                raise ValueError("Unverified asset market history")
            quality.append(meta)
        ledger = build_ledger(symbol, market, btc, as_of_ms, modeled_cost_bps)
        if not ledger["research_only"] or ledger["can_override_production"]:
            raise ValueError("Unsafe event ledger")
        ledgers.append(ledger)
    result = summarize(ledgers)
    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of_ms": as_of_ms,
        "calendar_days": days,
        "symbols": list(symbols),
        "data_quality": quality,
        "cost_assumption": {
            "modelled_roundtrip_bps": modeled_cost_bps,
            "source": "UNVALIDATED_RESEARCH_SCENARIO",
            "exchange_funding_unknown": True,
            "venue_orderbook_slippage_unknown": True,
        },
        "model_comparison": result,
        "overall_holdout": {
            p: result["by_segment"]["holdout"][p].get("ALL", _stats([]))
            for p in POLICIES
        },
        "discovery_reference": {
            p: result["by_segment"]["discovery"][p].get("ALL", _stats([]))
            for p in POLICIES
        },
        "causal_or_profitability_claim": False,
        "profitability_validated": False,
        "trade_ready": False,
        "can_change_production": False,
        "can_override_final_trade_gate": False,
        "can_create_trade": False,
        "research_only": True,
        "limitations": [
            "Data is Binance public spot candles, not execution-quality perpetual futures orderbook/funding",
            "Predeclared four baseline hypotheses, not an optimized trading strategy",
            "4h-spaced labels overlap in their 12h forward windows",
            "Cross-asset rows share BTC common shocks; counts are not independent trials",
            "Cost of 17bps is a scenario; modelled R is not realized profit",
            "Holdout comparison has no pre-existing blinded protocol independent of earlier 30d research",
            "Intrabar TP+SL cannot be ordered from 1h candles and is excluded",
            "No orders or account activity and no changes to Production decision authority",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=",".join(SYMBOLS))
    p.add_argument("--days", type=int, default=PREFROZEN_DAYS)
    p.add_argument("--cost-bps", type=float, default=BENCHMARK_COST_BPS)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    symbols = tuple(s.strip().upper() for s in args.symbols.split(",") if s.strip())
    report = build_market_audit(symbols, args.days, modeled_cost_bps=args.cost_bps)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "schema": report["schema"], "calendar_days": report["calendar_days"],
        "symbols": report["symbols"], "holdout": report["overall_holdout"],
        "profitability_validated": report["profitability_validated"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
