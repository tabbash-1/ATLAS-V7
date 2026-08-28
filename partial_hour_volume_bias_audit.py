#!/usr/bin/env python3
"""Research-only counterfactual audit for the historical partial-hour RV bug.

Replays existing Production snapshots. It never changes Production scoring,
thresholds, or execution. For pre-fix V6 observations it estimates the score
that the same observation would have received if the intended hourly volume
pacing had actually been active.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

V6_PREFIX = "PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE"
FIX_TAG = "PARTIAL_VOLUME_TIME_FIX_V1"
SCHEMA = "ATLAS_PARTIAL_HOUR_VOLUME_BIAS_AUDIT_V2_DENOMINATOR_AWARE"
DEFAULT_THRESHOLD = 68.0


def fnum(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def parse_time(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def hour_key(symbol, ts):
    return (symbol, ts.replace(minute=0, second=0, microsecond=0).isoformat())


def progress_from_timestamp(ts):
    """Approximate live 1h candle progress from the decision timestamp."""
    if ts is None:
        return None
    seconds = ts.minute * 60 + ts.second + ts.microsecond / 1_000_000
    return max(0.10, min(1.0, seconds / 3600.0))


def paced_rv(raw_rv, progress):
    raw = max(0.0, fnum(raw_rv, 0.0))
    p = max(0.10, min(1.0, fnum(progress, 1.0)))
    return min(4.0, raw / p)


def volume_bonus_v6(rv):
    return min(10.0, max(0.0, (fnum(rv, 0.0) - 1.0) * 10.0))


def round_score(v):
    return int(round(max(0.0, min(100.0, fnum(v, 0.0)))))


def progress_bucket(p):
    if p < 0.25:
        return "10-24%"
    if p < 0.50:
        return "25-49%"
    if p < 0.75:
        return "50-74%"
    return "75-100%"


def load_rows(path):
    rows = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def recovered_breakout(d, raw, paced):
    """Return whether RV pacing alone would recover breakout confirmation."""
    br = d.get("breakout_context") or {}
    if not br or br.get("confirmed") is True:
        return False
    if not (raw < 0.80 <= paced):
        return False
    if not bool(br.get("beyond_prior_24h_range")):
        return False
    votes = int(fnum(d.get("direction_votes"), 0) or 0)
    if votes != 4:
        return False
    direction = d.get("candidate_direction") or d.get("decision") or d.get("direction")
    mom = fnum(d.get("momentum_24h_pct"), 0.0) or 0.0
    if direction == "LONG" and mom <= 0:
        return False
    if direction == "SHORT" and mom >= 0:
        return False
    body_atr = fnum(br.get("current_body_atr"), 0.0) or 0.0
    # If body >= .35 ATR, volume was not the missing gate, so do not credit RV.
    return body_atr < 0.35


def summarise_group(items):
    if not items:
        return {"n": 0}
    deltas = [x["total_score_delta"] for x in items]
    direct = [x["direct_volume_score_delta"] for x in items]
    old_waits = sum(not bool(x["old_qualified"]) for x in items)
    flips = sum(bool(x["qualification_flip"]) for x in items)
    direct_flips = sum(bool(x["direct_volume_qualification_flip"]) for x in items)
    breakout_context_n = sum(bool(x.get("breakout_context_available")) for x in items)
    return {
        "n": len(items),
        "old_qualified": len(items) - old_waits,
        "old_waits": old_waits,
        "score_changed": sum(x > 0 for x in deltas),
        "qualification_flips": flips,
        "direct_volume_flips": direct_flips,
        "flip_rate_pct_among_old_waits": round(100.0 * flips / old_waits, 2) if old_waits else 0.0,
        "direct_flip_rate_pct_among_old_waits": round(100.0 * direct_flips / old_waits, 2) if old_waits else 0.0,
        "breakout_context_available": breakout_context_n,
        "breakout_context_coverage_pct": round(100.0 * breakout_context_n / len(items), 2),
        "breakout_recovered": sum(bool(x["breakout_recovered"]) for x in items),
        "rv_crossed_0_8": sum(bool(x["rv_crossed_0_8"]) for x in items),
        "rv_crossed_1_0": sum(bool(x["rv_crossed_1_0"]) for x in items),
        "rv_crossed_1_2": sum(bool(x["rv_crossed_1_2"]) for x in items),
        "mean_total_score_delta": round(mean(deltas), 4),
        "median_total_score_delta": round(median(deltas), 4),
        "max_total_score_delta": round(max(deltas), 4),
        "mean_direct_volume_delta": round(mean(direct), 4),
    }


def audit(rows):
    observations = []
    fixed_validation = []
    skipped = Counter()

    for snap in rows:
        captured = parse_time(snap.get("captured_at"))
        for symbol, d in (snap.get("decisions") or {}).items():
            if not isinstance(d, dict) or not d.get("ok"):
                continue
            version = str(d.get("scoring_version") or "")
            if not version.startswith(V6_PREFIX):
                continue
            ts = parse_time(d.get("generated_at")) or captured
            if ts is None:
                skipped["missing_timestamp"] += 1
                continue

            if FIX_TAG in version:
                raw = fnum(d.get("relative_volume_raw"))
                p = fnum(d.get("current_candle_progress"))
                actual = fnum(d.get("relative_volume"))
                # Decision API also exposes the same fields under volume_pacing;
                # support both shapes so later snapshots validate the live fix.
                vp = d.get("volume_pacing") or {}
                if raw is None:
                    raw = fnum(vp.get("raw_relative_volume"))
                if p is None:
                    p = fnum(vp.get("candle_progress"))
                if actual is None:
                    actual = fnum(vp.get("paced_relative_volume"))
                if raw is not None and p is not None and actual is not None:
                    expected = paced_rv(raw, p)
                    fixed_validation.append({
                        "symbol": symbol,
                        "generated_at": ts.isoformat(),
                        "raw_relative_volume": raw,
                        "progress": p,
                        "actual_paced_relative_volume": actual,
                        "expected_paced_relative_volume": expected,
                        "abs_error": abs(actual - expected),
                    })
                continue

            raw = fnum(d.get("relative_volume"))
            old_score = fnum(d.get("score"))
            attr = d.get("score_attribution") or {}
            if raw is None:
                skipped["missing_raw_relative_volume"] += 1
                continue
            if old_score is None:
                skipped["no_direction_or_no_score"] += 1
                continue

            p = progress_from_timestamp(ts)
            paced = paced_rv(raw, p)
            old_bonus = fnum(attr.get("volume_bonus"), volume_bonus_v6(raw))
            new_bonus = volume_bonus_v6(paced)
            direct_delta = max(0.0, new_bonus - old_bonus)

            breakout_context_available = bool(d.get("breakout_context"))
            br_recovered = recovered_breakout(d, raw, paced) if breakout_context_available else False
            obstacle_distance = fnum(attr.get("obstacle_distance_pct"))
            old_obstacle = fnum(attr.get("obstacle_adjustment"), 0.0) or 0.0
            # Current V6 grants +3 clear-space adjustment only when a confirmed
            # breakout has no prior obstacle ahead. Credit only that exact case.
            breakout_obstacle_delta = 0.0
            if br_recovered and obstacle_distance is None and old_obstacle < 3.0:
                breakout_obstacle_delta = 3.0 - old_obstacle

            raw_score = fnum(attr.get("raw_score"))
            base_score = raw_score if raw_score is not None else old_score
            direct_cf = round_score(base_score + direct_delta)
            full_cf = round_score(base_score + direct_delta + breakout_obstacle_delta)
            threshold = fnum(d.get("signal_threshold"), DEFAULT_THRESHOLD) or DEFAULT_THRESHOLD
            old_qualified = bool(d.get("signal_qualified") or d.get("production_signal_qualified") or old_score >= threshold)

            observations.append({
                "symbol": symbol,
                "generated_at": ts.isoformat(),
                "scoring_version": version,
                "candidate_direction": d.get("candidate_direction"),
                "old_score": old_score,
                "threshold": threshold,
                "old_qualified": old_qualified,
                "raw_relative_volume": round(raw, 6),
                "estimated_candle_progress": round(p, 6),
                "counterfactual_paced_relative_volume": round(paced, 6),
                "old_volume_bonus": round(old_bonus, 6),
                "counterfactual_volume_bonus": round(new_bonus, 6),
                "direct_volume_score_delta": round(direct_delta, 6),
                "breakout_context_available": breakout_context_available,
                "breakout_recovered": br_recovered,
                "breakout_obstacle_score_delta": round(breakout_obstacle_delta, 6),
                "total_score_delta": round(direct_delta + breakout_obstacle_delta, 6),
                "direct_counterfactual_score": direct_cf,
                "counterfactual_score": full_cf,
                "direct_volume_qualification_flip": bool(not old_qualified and direct_cf >= threshold),
                "qualification_flip": bool(not old_qualified and full_cf >= threshold),
                "rv_crossed_0_8": bool(raw < 0.80 <= paced),
                "rv_crossed_1_0": bool(raw < 1.00 <= paced),
                "rv_crossed_1_2": bool(raw < 1.20 <= paced),
                "progress_bucket": progress_bucket(p),
                "old_wait_reason": d.get("wait_reason"),
                "old_playbook": d.get("playbook"),
            })

    # System-behaviour counts use every actual observation; additionally create
    # an hourly de-duplicated view to prevent repeated runs in one hour from
    # exaggerating the finding.
    hourly = {}
    for x in observations:
        ts = parse_time(x["generated_at"])
        key = (x["symbol"], ts.replace(minute=0, second=0, microsecond=0).isoformat(), x.get("candidate_direction"), x["scoring_version"])
        # Keep the largest modeled impact in that hour; conservative for asking
        # whether the bug was capable of changing the decision during the hour.
        prev = hourly.get(key)
        if prev is None or x["total_score_delta"] > prev["total_score_delta"]:
            hourly[key] = x
    hourly_items = list(hourly.values())

    by_symbol = defaultdict(list)
    by_progress = defaultdict(list)
    for x in hourly_items:
        by_symbol[x["symbol"]].append(x)
        by_progress[x["progress_bucket"]].append(x)

    # Track upstream no-score WAIT states in the same time window using BOTH raw
    # observation count and unique symbol-hour count. The latter is the fairer
    # comparator to the hourly de-correlated score audit.
    no_consensus_raw = 0
    other_wait_without_score_raw = 0
    no_consensus_hours = set()
    other_no_score_hours = set()
    if observations:
        lo = min(parse_time(x["generated_at"]) for x in observations)
        hi = max(parse_time(x["generated_at"]) for x in observations)
        for snap in rows:
            captured = parse_time(snap.get("captured_at"))
            for symbol, d in (snap.get("decisions") or {}).items():
                if not isinstance(d, dict) or not d.get("ok"):
                    continue
                ts = parse_time(d.get("generated_at")) or captured
                if ts is None or ts < lo or ts > hi:
                    continue
                if d.get("score") is not None:
                    continue
                reason = d.get("wait_reason")
                if reason == "NO_DIRECTIONAL_CONSENSUS":
                    no_consensus_raw += 1
                    no_consensus_hours.add(hour_key(symbol, ts))
                elif reason:
                    other_wait_without_score_raw += 1
                    other_no_score_hours.add(hour_key(symbol, ts))
    else:
        lo = hi = None

    affected = sorted(
        hourly_items,
        key=lambda x: (x["qualification_flip"], x["total_score_delta"], x["counterfactual_paced_relative_volume"] - x["raw_relative_volume"]),
        reverse=True,
    )[:30]

    validation_max_error = max((x["abs_error"] for x in fixed_validation), default=None)
    validation_mean_error = mean([x["abs_error"] for x in fixed_validation]) if fixed_validation else None
    hourly_summary = summarise_group(hourly_items)
    breakout_coverage = hourly_summary.get("breakout_context_coverage_pct", 0.0)

    return {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "Quantify how the historical live partial-hour RV timestamp bug biased V6 score/WAIT behavior using existing Production snapshots only.",
        "method": {
            "pre_fix_scope": f"scoring_version starts {V6_PREFIX} and excludes {FIX_TAG}",
            "progress_estimate": "decision generated_at minute+second within the UTC hour, bounded 0.10..1.00",
            "paced_rv_formula": "min(4.0, raw_rv / progress)",
            "direct_score_replay": "historical raw_score + (V6 volume_bonus(paced_rv) - historical volume_bonus)",
            "breakout_replay": "only evaluated where historical breakout_context exists; otherwise breakout effect is UNKNOWN, not zero",
            "hourly_independence": "de-duplicate symbol+UTC-hour+direction+scoring-version; retain largest modeled impact within hour",
        },
        "guardrails": {
            "research_only": True,
            "production_threshold_changed": False,
            "scoring_weights_changed": False,
            "auto_promotion": False,
            "live_execution": False,
        },
        "pre_fix_window": {"start": lo.isoformat() if lo else None, "end": hi.isoformat() if hi else None},
        "raw_observations": summarise_group(observations),
        "independent_hourly_observations": hourly_summary,
        "wait_attribution": {
            "scored_directional_wait_hours": hourly_summary.get("old_waits", 0),
            "volume_direct_qualification_flip_hours": hourly_summary.get("direct_volume_flips", 0),
            "volume_direct_flip_rate_pct_among_scored_wait_hours": hourly_summary.get("direct_flip_rate_pct_among_old_waits", 0.0),
            "no_directional_consensus_raw_observations": no_consensus_raw,
            "no_directional_consensus_unique_symbol_hours": len(no_consensus_hours),
            "other_wait_without_score_raw_observations": other_wait_without_score_raw,
            "other_wait_without_score_unique_symbol_hours": len(other_no_score_hours),
            "interpretation": "NO_DIRECTIONAL_CONSENSUS is upstream of volume scoring and cannot be fixed by the partial-hour RV correction. Unique symbol-hours are the fair comparator; raw counts are shown only for transparency.",
        },
        "breakout_replay_coverage": {
            "hourly_context_available": hourly_summary.get("breakout_context_available", 0),
            "hourly_context_coverage_pct": breakout_coverage,
            "recovered_breakouts_observed": hourly_summary.get("breakout_recovered", 0),
            "interpretation": "If coverage is low, recovered_breakouts_observed is an under-observed lower bound and must not be interpreted as proof of zero breakout impact.",
        },
        "by_symbol_hourly": {k: summarise_group(v) for k, v in sorted(by_symbol.items())},
        "by_candle_progress_hourly": {k: summarise_group(v) for k, v in sorted(by_progress.items())},
        "post_fix_formula_validation": {
            "n": len(fixed_validation),
            "mean_abs_rv_error": round(validation_mean_error, 8) if validation_mean_error is not None else None,
            "max_abs_rv_error": round(validation_max_error, 8) if validation_max_error is not None else None,
            "formula_matches_within_0_002": bool(fixed_validation and validation_max_error <= 0.002),
            "note": "n=0 means no post-fix candidate row with both raw/progress fields existed in the checked-in history at replay time; live Render smoke is a separate validation path.",
        },
        "most_affected_hourly_examples": affected,
        "skipped": dict(skipped),
        "decision_rule": "Use this audit to diagnose historical WAIT/score bias only. Do not lower threshold 68 or tune weights from this report.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="status/history/production-snapshots.jsonl")
    ap.add_argument("--output", default="status/partial-hour-volume-bias-audit.json")
    args = ap.parse_args()
    report = audit(load_rows(args.input))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({
        "schema": report["schema"],
        "pre_fix_window": report["pre_fix_window"],
        "hourly": report["independent_hourly_observations"],
        "wait_attribution": report["wait_attribution"],
        "breakout_replay_coverage": report["breakout_replay_coverage"],
        "post_fix_formula_validation": report["post_fix_formula_validation"],
    }, indent=2))


if __name__ == "__main__":
    main()
