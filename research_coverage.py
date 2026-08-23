"""Coverage helpers for ATLAS research-only forward sampling.

This module does not create trade signals. It only prevents the research
sampling lane from repeatedly selecting the same highest-score assets while
other supported assets receive no observations.
"""

from __future__ import annotations


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_cloud_research_row(row):
    if not isinstance(row, dict):
        return False
    source = str(row.get("auto_source") or "")
    return source.startswith("CLOUD_FORWARD") or bool(row.get("research_sampling_lane"))


def build_coverage(rows, symbols, now_ms, stale_hours=8.0):
    """Return persistent per-asset cloud-research coverage diagnostics."""
    by_symbol = {
        str(symbol): {
            "observations": 0,
            "last_seen_ms": None,
            "age_hours": None,
            "never_seen": True,
            "stale": True,
        }
        for symbol in symbols
    }
    for row in rows or []:
        if not is_cloud_research_row(row):
            continue
        symbol = str(row.get("symbol") or "")
        if symbol not in by_symbol:
            continue
        ts = int(_num(row.get("captured_at_ms"), 0))
        item = by_symbol[symbol]
        item["observations"] += 1
        if ts and (item["last_seen_ms"] is None or ts > item["last_seen_ms"]):
            item["last_seen_ms"] = ts

    stale_ms = max(1.0, _num(stale_hours, 8.0)) * 3600 * 1000
    for item in by_symbol.values():
        ts = item["last_seen_ms"]
        item["never_seen"] = ts is None
        if ts is None:
            item["age_hours"] = None
            item["stale"] = True
        else:
            age_ms = max(0, int(now_ms) - int(ts))
            item["age_hours"] = round(age_ms / 3600000, 2)
            item["stale"] = age_ms >= stale_ms
    return by_symbol


def choose_research_samples(pool, limit, signal_keys, coverage):
    """Choose research rows by coverage first, score second.

    Priority order:
    1. assets never observed,
    2. assets with the fewest observations,
    3. oldest last observation,
    4. stronger research score as a final tie-breaker.

    Signal-qualified rows already selected by the strict signal lane are
    excluded because they already create a forward observation for coverage.
    """
    signal_keys = set(signal_keys or ())
    candidates = []
    for row in pool or []:
        key = (row.get("symbol"), row.get("direction"))
        if key in signal_keys:
            continue
        symbol = str(row.get("symbol") or "")
        cov = (coverage or {}).get(symbol, {})
        count = int(_num(cov.get("observations"), 0))
        last_seen = cov.get("last_seen_ms")
        never = 0 if last_seen is None else 1
        oldest = int(last_seen or 0)
        score = _num(row.get("final_score"), 0)
        candidates.append(((never, count, oldest, -score), row))
    candidates.sort(key=lambda item: item[0])
    return [row for _, row in candidates[: max(0, int(limit or 0))]]


def coverage_summary(coverage):
    coverage = coverage or {}
    never = [s for s, x in coverage.items() if x.get("never_seen")]
    stale = [s for s, x in coverage.items() if x.get("stale") and not x.get("never_seen")]
    counts = {s: int(_num(x.get("observations"), 0)) for s, x in coverage.items()}
    return {
        "covered_assets": sum(1 for x in coverage.values() if not x.get("never_seen")),
        "total_assets": len(coverage),
        "never_seen_assets": never,
        "stale_assets": stale,
        "observation_counts": counts,
        "complete": not never,
        "fresh": not never and not stale,
    }
