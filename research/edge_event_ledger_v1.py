#!/usr/bin/env python3
"""Research-only all-market event ledger for ATLAS 4–12H path discovery.

Labels *both* hypothetical directions on regularly sampled closed 1H bars,
rather than studying only historical TRADE_READY picks. This intentionally
does not recommend a trade, fit a model, change Production, or claim an edge.
Features are frozen at the close of the observation candle. Future OHLC bars
are only used for settlement. Overlapping observations are not independent.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

SCHEMA = "ATLAS_EDGE_EVENT_LEDGER_V1"
HOUR_MS = 3_600_000
HORIZON_H = 12
STEP_H = 4
STOP_ATR = 1.5
TARGET_R = 2.5
MIN_HISTORY = 30


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError("OHLCV contains a nonnumeric value")
    if not math.isfinite(value):
        raise ValueError("OHLCV contains a nonfinite value")
    return value


def normalize_candles(items, as_of_ms):
    """Only completed, uninterrupted, chronologically ordered 1H candles."""
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Candle must be a dict")
        t = int(item["time"])
        end = int(item["close_time"])
        if end - t not in (HOUR_MS - 1, HOUR_MS):
            raise ValueError("Expected 1H close-time semantics")
        values = {k: _number(item[k]) for k in ("open", "high", "low", "close", "volume")}
        if values["low"] <= 0 or values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]) or values["volume"] < 0:
            raise ValueError("Invalid candle prices or volume")
        if result and t - result[-1]["time"] != HOUR_MS:
            raise ValueError("Duplicate, missing or unsorted 1H candles")
        if end <= as_of_ms:
            result.append({"time": t, "close_time": end, **values})
    return result


def _atr(candles, i):
    values = []
    for k in range(i - 13, i + 1):
        bar = candles[k]
        pc = candles[k - 1]["close"]
        values.append(max(bar["high"] - bar["low"], abs(bar["high"] - pc), abs(bar["low"] - pc)))
    return sum(values) / len(values)


def _pct(now, prior):
    return round(100 * (now / prior - 1), 6)


def frozen_features(market, btc, index, btc_index):
    """Read only candles with index <= observation (no target look-ahead)."""
    if index < MIN_HISTORY or btc_index < MIN_HISTORY:
        raise ValueError("Insufficient closed-bar history")
    px = market[index]["close"]
    bpx = btc[btc_index]["close"]
    atr = _atr(market, index)
    base_vol = sum(c["volume"] for c in market[index - 20:index]) / 20
    return {
        "observed_close_time_ms": market[index]["close_time"],
        "asset_return_1h_pct": _pct(px, market[index - 1]["close"]),
        "asset_return_4h_pct": _pct(px, market[index - 4]["close"]),
        "asset_return_12h_pct": _pct(px, market[index - 12]["close"]),
        "btc_return_4h_pct": _pct(bpx, btc[btc_index - 4]["close"]),
        "btc_return_12h_pct": _pct(bpx, btc[btc_index - 12]["close"]),
        "relative_volume_1h": round(market[index]["volume"] / base_vol, 6) if base_vol else None,
        "atr14": round(atr, 10),
        "atr_pct": round(100 * atr / px, 6),
        "extension_atr_from_20h_mean": round(
            (px - sum(c["close"] for c in market[index - 19:index + 1]) / 20) / atr, 6
        ) if atr > 0 else None,
    }


def settle_path(future, direction, reference_entry, stop, target, cost_bps=None):
    """Settle in timestamp order; same-hour TP+SL is ambiguous, NEVER a win.

    Entry assumes a hypothetical market fill at the next candle's open.
    Geometry was frozen from the prior completed close, without future data.
    A first-open gap across either planned barrier invalidates the entry.
    """
    if direction not in ("LONG", "SHORT") or len(future) != HORIZON_H:
        raise ValueError("Invalid direction or incomplete 12h forward window")
    first_open = future[0]["open"]
    if direction == "LONG":
        risk = first_open - stop
        gap_invalid = first_open <= stop or first_open >= target
    else:
        risk = stop - first_open
        gap_invalid = first_open >= stop or first_open <= target
    if gap_invalid or risk <= 0:
        return {"outcome": "GAP_UNEXECUTABLE", "gross_r": None, "modeled_net_r": None}
    out = None
    exit_price = None
    for bar in future:
        # Price gaps in an *already-entered* position settle at the actual open
        # on adverse moves. A favorable gap takes only the frozen target.
        if direction == "LONG":
            open_stop, open_tp = bar["open"] <= stop, bar["open"] >= target
            hit_stop, hit_tp = bar["low"] <= stop, bar["high"] >= target
        else:
            open_stop, open_tp = bar["open"] >= stop, bar["open"] <= target
            hit_stop, hit_tp = bar["high"] >= stop, bar["low"] <= target
        if open_stop:
            out, exit_price = "SL_FIRST", bar["open"]
        elif open_tp:
            out, exit_price = "TP_FIRST", target
        elif hit_stop and hit_tp:
            out = "AMBIGUOUS_INTRABAR_ORDER"
        elif hit_stop:
            out, exit_price = "SL_FIRST", stop
        elif hit_tp:
            out, exit_price = "TP_FIRST", target
        if out:
            break
    if not out:
        out, exit_price = "EXPIRED_12H", future[-1]["close"]
    if exit_price is None:
        return {"outcome": out, "gross_r": None, "modeled_net_r": None}
    sign = 1 if direction == "LONG" else -1
    gross = sign * (exit_price - first_open) / risk
    modeled_cost_r = (first_open * cost_bps / 10_000) / risk if cost_bps is not None else None
    return {
        "outcome": out,
        "gross_r": round(gross, 6),
        "modeled_net_r": round(gross - modeled_cost_r, 6) if modeled_cost_r is not None else None,
        "hypothetical_fill_open": round(first_open, 10),
        "modeled_cost_only_not_venue_validated": cost_bps is not None,
    }


def build_ledger(symbol, raw_market, raw_btc, as_of_ms, modeled_cost_bps=None):
    if modeled_cost_bps is not None and (modeled_cost_bps < 0 or modeled_cost_bps > 100):
        raise ValueError("Cost scenario must be 0-100 basis points")
    market = normalize_candles(raw_market, as_of_ms)
    btc = normalize_candles(raw_btc, as_of_ms)
    btc_index_by_close = {b["close_time"]: i for i, b in enumerate(btc)}
    rows = []
    skipped_no_btc = 0
    for i in range(MIN_HISTORY, len(market) - HORIZON_H, STEP_H):
        bi = btc_index_by_close.get(market[i]["close_time"])
        if bi is None or bi < MIN_HISTORY:
            skipped_no_btc += 1
            continue
        features = frozen_features(market, btc, i, bi)
        atr = features["atr14"]
        if atr <= 0:
            continue
        entry_ref = market[i]["close"]
        risk = STOP_ATR * atr
        forward = market[i + 1:i + 1 + HORIZON_H]
        if len(forward) != HORIZON_H:
            continue
        for direction in ("LONG", "SHORT"):
            sign = 1 if direction == "LONG" else -1
            stop = entry_ref - sign * risk
            tp = entry_ref + sign * risk * TARGET_R
            if stop <= 0 or tp <= 0:
                continue
            result = settle_path(forward, direction, entry_ref, stop, tp, modeled_cost_bps)
            rows.append({
                "symbol": symbol, "direction": direction,
                "event_at_ms": market[i]["close_time"],
                "forward_matures_at_ms": forward[-1]["close_time"],
                "features": features,
                "frozen_plan": {
                    "entry_reference": round(entry_ref, 10),
                    "stop_loss": round(stop, 10),
                    "take_profit": round(tp, 10),
                    "stop_atr": STOP_ATR, "gross_target_r": TARGET_R,
                },
                "settlement": result,
                "hypothetical_research_only": True,
                "eligible_for_paper_portfolio": False,
            })
    outcomes = Counter(r["settlement"]["outcome"] for r in rows)
    costed = [r["settlement"]["modeled_net_r"] for r in rows if r["settlement"]["modeled_net_r"] is not None]
    return {
        "schema": SCHEMA, "symbol": symbol, "as_of_ms": as_of_ms,
        "product_horizon": "4-12H", "label_horizon_hours": HORIZON_H,
        "event_spacing_hours": STEP_H,
        "overlapping_event_outcomes_not_independent": True,
        "entry_model": "HYPOTHETICAL_NEXT_1H_OPEN_FROZEN_CLOSE_LEVELS",
        "market_observation_count": len(market),
        "btc_observation_count": len(btc),
        "skipped_no_aligned_btc": skipped_no_btc,
        "paired_directions_per_event": 2,
        "outcome_counts": dict(sorted(outcomes.items())),
        "modeled_cost_bps": modeled_cost_bps,
        "modeled_net_r_mean_descriptive_only": round(sum(costed) / len(costed), 6) if costed else None,
        "limitations": [
            "Hypothetical market entries, not an ATLAS Production trade or paper execution",
            "1H intrabar double touches are ambiguous and excluded from R calculations",
            "Costs are scenarios, not verified venue quotes",
            "Dependent overlapping events cannot support naive confidence intervals",
            "No strategy selection, model calibration, financial edge claim, or production promotion",
        ],
        "can_override_production": False,
        "can_change_threshold": False,
        "can_create_trade": False,
        "live_execution": False,
        "research_only": True,
        "profitability_validated": False,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-json", required=True)
    parser.add_argument("--btc-json", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--as-of-ms", required=True, type=int)
    parser.add_argument("--modeled-cost-bps", type=float, default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    market = json.loads(Path(args.market_json).read_text())
    btc = json.loads(Path(args.btc_json).read_text())
    out = build_ledger(args.symbol, market, btc, args.as_of_ms, args.modeled_cost_bps)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("schema", "symbol", "outcome_counts", "profitability_validated")}, sort_keys=True))


if __name__ == "__main__":
    main()
