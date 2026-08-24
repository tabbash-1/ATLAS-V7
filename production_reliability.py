"""ATLAS production reliability hardening.

This layer keeps Production qualification unchanged while fixing four operational
problems:
1. data integrity is no longer conflated with evidence/sample maturity;
2. Smart-Money warm-up captures the whole universe concurrently after boot;
3. HYPE gets a Hyperliquid public perpetual fallback when CEX futures fail;
4. WAIT responses expose a frozen conditional action from the existing AI
   counterfactual engine without changing the Production threshold.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request

VERSION = "PRODUCTION_RELIABILITY_V1"
FRESH_SMART_MONEY_HOURS = 6.0


def _post_json(url, payload, ua, timeout=18):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"User-Agent": ua, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _hyperliquid_hype_capture(atlas):
    """Provider-specific HYPE perp context. Shadow-only for Production scoring."""
    meta_ctx = _post_json("https://api.hyperliquid.xyz/info", {"type": "metaAndAssetCtxs"}, atlas.UA)
    if not isinstance(meta_ctx, list) or len(meta_ctx) < 2:
        raise RuntimeError("Hyperliquid metaAndAssetCtxs returned invalid payload")
    meta, contexts = meta_ctx[0], meta_ctx[1]
    universe = (meta or {}).get("universe") or []
    index = next((i for i, row in enumerate(universe) if str(row.get("name", "")).upper() == "HYPE"), None)
    if index is None or index >= len(contexts):
        raise RuntimeError("Hyperliquid HYPE perpetual context missing")
    ctx = contexts[index] or {}
    book = _post_json("https://api.hyperliquid.xyz/info", {"type": "l2Book", "coin": "HYPE"}, atlas.UA)
    levels = (book or {}).get("levels") or [[], []]
    bids_raw = levels[0] if len(levels) > 0 else []
    asks_raw = levels[1] if len(levels) > 1 else []
    bids = [[x.get("px"), x.get("sz")] for x in bids_raw if isinstance(x, dict)]
    asks = [[x.get("px"), x.get("sz")] for x in asks_raw if isinstance(x, dict)]
    depth = {"bids": bids, "asks": asks}
    bidn, askn, imbalance = atlas.orderbook_metrics(depth)
    mark = atlas.fnum(ctx.get("markPx"))
    oracle = atlas.fnum(ctx.get("oraclePx"))
    walls = atlas.liquidity_walls(depth, mark)
    oi = atlas.fnum(ctx.get("openInterest"))
    prev = atlas.previous_provider("HYPEUSDT", "HYPERLIQUID_PERP_PUBLIC")
    prev_oi = atlas.fnum(prev.get("open_interest")) if prev else None
    oi_change = ((oi / prev_oi - 1) * 100) if oi is not None and prev_oi else None
    funding = atlas.fnum(ctx.get("funding"))
    day_volume = atlas.fnum(ctx.get("dayNtlVlm"))
    # Hyperliquid public context does not provide the same Binance taker-ratio
    # semantic here, so keep it neutral rather than fabricating directional flow.
    taker_ratio = 1.0
    score = atlas.score_snapshot(funding, taker_ratio, imbalance, oi_change)
    return {
        "schema": "ATLAS_SM_V2",
        "captured_at": atlas.now_iso(),
        "captured_at_ms": int(time.time() * 1000),
        "symbol": "HYPEUSDT",
        "mark_price": mark,
        "index_price": oracle,
        "funding_rate": funding,
        "next_funding_time": None,
        "open_interest": oi,
        "oi_change_pct": round(oi_change, 5) if oi_change is not None else None,
        "taker_ratio": taker_ratio,
        "taker_buy_vol": None,
        "taker_sell_vol": None,
        "orderbook_bid_notional_top20": round(bidn, 2),
        "orderbook_ask_notional_top20": round(askn, 2),
        "orderbook_imbalance": round(imbalance, 6),
        "orderbook_bid_walls": walls["bid_walls"],
        "orderbook_ask_walls": walls["ask_walls"],
        "price_change_24h_pct": None,
        "quote_volume_24h": day_volume,
        "experimental_score": score,
        "factor_label": "EXPERIMENTAL_PROVIDER_SPECIFIC_UNVALIDATED",
        "whale_exchange_flow": None,
        "whale_provider_status": "NOT_CONNECTED",
        "live_execution": False,
        "futures_provider": "HYPERLIQUID_PERP_PUBLIC",
        "futures_evidence_validated": False,
        "flow_proxy": "NEUTRAL_NO_EQUIVALENT_TAKER_RATIO",
        "sources": ["Hyperliquid public info API: metaAndAssetCtxs + l2Book"],
    }


def _integrity_quality(atlas, original_report):
    base = original_report()
    forward = atlas.read_forward()
    smart = atlas.read_all()
    now_ms = int(time.time() * 1000)

    missing_entry = sum(1 for row in forward if atlas.fnum(row.get("entry")) is None)
    missing_direction = sum(1 for row in forward if row.get("direction") not in ("LONG", "SHORT"))
    duplicate_keys = {}
    for row in forward:
        key = (row.get("symbol"), row.get("direction"), int(row.get("captured_at_ms", 0)) // (50 * 60 * 1000))
        duplicate_keys[key] = duplicate_keys.get(key, 0) + 1
    duplicate_buckets = sum(1 for value in duplicate_keys.values() if value > 1)

    counts = {symbol: 0 for symbol in atlas.ON_DEMAND_SYMBOLS}
    fresh = {}
    providers = {}
    validated = {}
    for row in smart:
        symbol = row.get("symbol")
        if symbol in counts:
            counts[symbol] += 1
        provider = row.get("futures_provider") or "BINANCE_USDM_PUBLIC"
        providers[provider] = providers.get(provider, 0) + 1
    for symbol in atlas.ON_DEMAND_SYMBOLS:
        rows = [row for row in smart if row.get("symbol") == symbol]
        last = rows[-1] if rows else None
        age = ((now_ms - int(last.get("captured_at_ms", 0))) / 3600000) if last else None
        fresh[symbol] = bool(last and age is not None and age <= FRESH_SMART_MONEY_HOURS)
        validated[symbol] = bool(last and last.get("futures_evidence_validated"))

    # Integrity score only. Evidence maturity and provider breadth are surfaced
    # separately and must not masquerade as corrupt data.
    quality = 100
    quality -= min(25, missing_entry * 3)
    quality -= min(20, missing_direction * 3)
    quality -= min(20, duplicate_buckets * 2)
    quality = max(0, quality)
    integrity_issues = []
    if missing_entry:
        integrity_issues.append(f"{missing_entry} forward rows missing entry")
    if missing_direction:
        integrity_issues.append(f"{missing_direction} forward rows missing direction")
    if duplicate_buckets:
        integrity_issues.append(f"{duplicate_buckets} duplicate 50m buckets")

    fresh_assets = [s for s, ok in fresh.items() if ok]
    missing_fresh = [s for s, ok in fresh.items() if not ok]
    evidence_maturity = "VALIDATION_SAMPLE" if len(forward) >= 100 else "EARLY_SAMPLE" if len(forward) >= 30 else "COLLECTING"
    coverage_status = "COMPLETE" if not missing_fresh else "WARMING" if fresh_assets else "UNAVAILABLE"

    result = dict(base)
    result.update({
        "quality_score": quality,
        "status": "HEALTHY" if quality >= 90 else "WATCH" if quality >= 65 else "DEGRADED",
        "quality_scope": "DATA_INTEGRITY_ONLY",
        "issues": integrity_issues,
        "integrity_issues": integrity_issues,
        "evidence_maturity": evidence_maturity,
        "evidence_forward_rows": len(forward),
        "smart_money_counts_all_assets": counts,
        "smart_money_fresh_by_asset": fresh,
        "smart_money_missing_fresh_assets": missing_fresh,
        "smart_money_coverage_status": coverage_status,
        "smart_money_fresh_coverage_pct": round(len(fresh_assets) / max(1, len(counts)) * 100, 2),
        "validated_futures_by_asset": validated,
        "provider_counts": providers,
        "reliability_version": VERSION,
    })
    return result


def _conditional_wait(atlas, decision):
    if not isinstance(decision, dict) or not decision.get("ok"):
        return decision
    # Preserve the canonical Production result byte-for-byte semantically; only
    # attach a conditional action when Production is not execution-ready.
    if decision.get("actionable_decision") != "WAIT":
        decision["conditional_wait"] = {"status": "NOT_NEEDED", "production_unchanged": True}
        return decision
    direction = decision.get("candidate_direction")
    if direction not in ("LONG", "SHORT"):
        decision["conditional_wait"] = {"status": "NO_DIRECTION", "production_unchanged": True}
        return decision
    try:
        import ai_trade_council
        council = ai_trade_council.analyze(decision)
        scenarios = council.get("counterfactuals") or []
        candidates = [
            row for row in scenarios
            if row.get("scenario") in ("WAIT_PULLBACK", "WAIT_BREAKOUT")
            and atlas.fnum(row.get("risk_reward")) is not None
            and atlas.fnum(row.get("risk_reward")) >= 1.0
        ]
        candidates.sort(key=lambda row: atlas.fnum(row.get("risk_reward"), 0), reverse=True)
        best = candidates[0] if candidates else None
        if best:
            decision["conditional_wait"] = {
                "status": "ARMED_SHADOW_CONDITION",
                "direction": direction,
                "scenario": best.get("scenario"),
                "trigger": best.get("trigger"),
                "entry": best.get("entry"),
                "stop_loss": best.get("stop_loss"),
                "target": best.get("target"),
                "risk_reward": best.get("risk_reward"),
                "requires_requalification": True,
                "requalification_threshold": decision.get("signal_threshold"),
                "production_unchanged": True,
                "can_execute": False,
                "shadow_only": True,
            }
        else:
            decision["conditional_wait"] = {
                "status": "NO_ACCEPTABLE_CONDITIONAL_GEOMETRY",
                "requires_requalification": True,
                "production_unchanged": True,
                "can_execute": False,
                "shadow_only": True,
            }
    except Exception as exc:
        decision["conditional_wait"] = {
            "status": "UNAVAILABLE",
            "error": f"{type(exc).__name__}: {exc}",
            "production_unchanged": True,
            "can_execute": False,
            "shadow_only": True,
        }
    return decision


def install(atlas):
    state = {
        "enabled": True,
        "version": VERSION,
        "parallel_warmup": True,
        "hype_hyperliquid_fallback": True,
        "actionable_wait": True,
        "warmup_cycles": 0,
        "last_warmup_started_at": None,
        "last_warmup_finished_at": None,
        "last_warmup_successes": [],
        "last_warmup_failures": {},
    }

    original_capture = atlas.capture
    original_quality = atlas.data_quality_report
    original_handler = atlas.Handler.do_GET

    def capture(symbol):
        try:
            return original_capture(symbol)
        except Exception as primary:
            if str(symbol).upper().replace("BINANCE:", "") != "HYPEUSDT":
                raise
            try:
                snap = _hyperliquid_hype_capture(atlas)
                with atlas.ARCHIVE_LOCK:
                    with atlas.ARCHIVE.open("a") as handle:
                        handle.write(json.dumps(snap, separators=(",", ":")) + "\n")
                atlas.MARKET_DATA_STATE["futures"]["last_provider"] = "api.hyperliquid.xyz"
                atlas.MARKET_DATA_STATE["futures"]["last_success_at"] = atlas.now_iso()
                atlas.MARKET_DATA_STATE["futures"]["last_error"] = None
                return snap
            except Exception as fallback:
                raise RuntimeError(f"HYPE futures providers failed: {primary} | Hyperliquid fallback failed: {fallback}")

    atlas.capture = capture

    def data_quality_report():
        return _integrity_quality(atlas, original_quality)

    atlas.data_quality_report = data_quality_report

    def parallel_auto_loop():
        time.sleep(1)
        while True:
            atlas.SMART_MONEY_STATE["last_started_at"] = atlas.now_iso()
            state["last_warmup_started_at"] = atlas.now_iso()
            successes = []
            failures = {}
            lock = threading.Lock()

            def one(symbol):
                try:
                    atlas.capture(symbol)
                    with lock:
                        successes.append(symbol)
                        atlas.SMART_MONEY_STATE["captures"] += 1
                except Exception as exc:
                    with lock:
                        failures[symbol] = f"{type(exc).__name__}: {exc}"
                        atlas.SMART_MONEY_STATE["errors"] += 1

            threads = [threading.Thread(target=one, args=(symbol,), daemon=True, name=f"atlas-sm-{symbol}") for symbol in atlas.SYMBOLS]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=35)

            atlas.SMART_MONEY_STATE["cycles"] += 1
            state["warmup_cycles"] += 1
            state["last_warmup_successes"] = sorted(successes)
            state["last_warmup_failures"] = failures
            state["last_warmup_finished_at"] = atlas.now_iso()
            if successes:
                atlas.SMART_MONEY_STATE["last_success_at"] = atlas.now_iso()
            atlas.SMART_MONEY_STATE["last_error"] = None if not failures else " | ".join(f"{k}: {v}" for k, v in failures.items())
            time.sleep(atlas.INTERVAL_SECONDS)

    atlas.auto_loop = parallel_auto_loop

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/decision/current":
            q = urllib.parse.parse_qs(u.query)
            symbol = q.get("symbol", ["BTCUSDT"])[0]
            try:
                result = _conditional_wait(atlas, atlas.production_decision(symbol))
                result["reliability_version"] = VERSION
                return self._json(result, 200 if result.get("ok") else 400)
            except Exception as exc:
                return self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}", "source": VERSION, "research_only": True, "live_execution": False}, 500)
        if u.path == "/api/reliability/status":
            quality = atlas.data_quality_report()
            return self._json({"ok": True, **state, "data_quality": quality, "research_only": True, "live_execution": False}, 200)
        return original_handler(self)

    atlas.Handler.do_GET = do_GET
    atlas.PRODUCTION_RELIABILITY_STATE = state
    return state
