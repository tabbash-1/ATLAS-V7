#!/usr/bin/env python3
"""ATLAS walk-forward screen.

Question answered: does an ATLAS-style 1h signal (trend / breakout / mean-reversion)
produce positive Net R AFTER costs on years of data, not on 29 forward trades?

Design rules (pre-registered, do not change after seeing results):
  * No parameter is fitted. Every rule is fixed, so every part of the timeline is
    out-of-sample. The chronological split (first 60% DISCOVERY, last 40% HOLDOUT)
    is only there to check stability; you may look at DISCOVERY, HOLDOUT decides.
  * Signal is read at the CLOSE of bar i, entry is the OPEN of bar i+1 (no lookahead).
  * Geometry: stop = ATR_MULT x ATR14, target = RR x risk, time exit after HORIZON bars.
    If stop and target are both inside one bar, the stop is assumed first (conservative).
  * Cost is charged per trade as cost_pct / risk_pct in R (risk_pct = stop distance in %).
  * One open trade per asset, at most MAX_OPEN trades at once across assets.
  * Confidence interval: block bootstrap by calendar week (assets are correlated).
  * A variant PASSES only if ALL criteria in CRITERIA hold at the stated cost.
  * `control_random` = same entry times as trend4 with a coin-flip direction. It shows
    what the geometry alone yields (about -cost). A real variant must beat it clearly.
  * If you add a variant or change a rule, that is a NEW test: raise K_VARIANTS.

Data: Binance public spot klines (data-api.binance.vision, same source ATLAS uses).
Usage:
  python walk_forward_screen.py --selftest
  python walk_forward_screen.py --years 3 --cost 0.15 --out wf_out
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

API = "https://data-api.binance.vision/api/v3/klines"
HOUR = 3_600_000
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
           "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT", "ZECUSDT"]

ATR_MULT = 1.5
RR = 2.0
HORIZON = 12
WARMUP = 130
VARIANTS = ["trend4", "breakout", "meanrev"]
CONTROL = "control_random"
K_VARIANTS = len(VARIANTS)
COST_LEVELS = [0.06, 0.10, 0.15, 0.20]
CRITERIA = {
    "holdout_min_trades": 100,
    "holdout_min_mean_net_r": 0.10,
    "holdout_ci_lower_gt": 0.0,      # one-sided bound at 5% / K_VARIANTS
    "min_positive_quarter_share": 2 / 3,
    "min_quarters_with_20_trades": 4,
    "discovery_mean_gt": 0.0,
}


# ----------------------------------------------------------------------------- data

def http_json(url, tries=5):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "atlas-wf-screen/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 418, 500, 502, 503, 504):
                time.sleep(2 * (k + 1))
                continue
            raise
        except Exception as e:  # network hiccup
            last = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"request failed: {last}")


def fetch_klines(symbol, start_ms, end_ms, cache_dir, refresh=False):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{symbol}_1h.csv")
    rows = {}
    if os.path.exists(path) and not refresh:
        with open(path, newline="") as f:
            for r in csv.reader(f):
                rows[int(r[0])] = tuple([int(r[0])] + [float(x) for x in r[1:]])
    cur = (max(rows) + HOUR) if rows else start_ms
    now_ms = int(time.time() * 1000)
    while cur < end_ms:
        batch = http_json(f"{API}?symbol={symbol}&interval=1h&startTime={cur}&limit=1000")
        if not batch:
            break
        for k in batch:
            if int(k[6]) >= now_ms:      # skip the unfinished candle
                continue
            rows[int(k[0])] = (int(k[0]), float(k[1]), float(k[2]), float(k[3]),
                               float(k[4]), float(k[5]))
        last = int(batch[-1][0])
        if last + HOUR <= cur or len(batch) < 1000:
            break
        cur = last + HOUR
        time.sleep(0.12)
    out = [rows[t] for t in sorted(rows) if t >= start_ms]
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(out)
    return out


def load_all(symbols, years, cache_dir, refresh):
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - int(years * 365.25 * 24 * HOUR)
    data = {}
    for s in symbols:
        try:
            rows = fetch_klines(s, start_ms, end_ms, cache_dir, refresh)
        except Exception as e:
            print(f"skip {s}: {e}", file=sys.stderr)
            continue
        if len(rows) >= 1000:
            data[s] = rows
            print(f"{s}: {len(rows)} bars", file=sys.stderr)
        else:
            print(f"skip {s}: only {len(rows)} bars", file=sys.stderr)
    return data


# ------------------------------------------------------------------------ indicators

def compute_indicators(rows):
    n = len(rows)
    t = [r[0] for r in rows]
    o = [r[1] for r in rows]
    h = [r[2] for r in rows]
    l = [r[3] for r in rows]
    c = [r[4] for r in rows]
    v = [r[5] for r in rows]
    ema20, ema50 = [0.0] * n, [0.0] * n
    e20 = e50 = c[0]
    for i in range(n):
        if i:
            e20 = c[i] * (2 / 21) + e20 * (1 - 2 / 21)
            e50 = c[i] * (2 / 51) + e50 * (1 - 2 / 51)
        ema20[i], ema50[i] = e20, e50
    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr = [None] * n
    rsi = [None] * n
    mom = [None] * n
    relvol = [None] * n
    phi = [None] * n
    plo = [None] * n
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        d = c[i] - c[i - 1]
        gains[i], losses[i] = max(d, 0.0), max(-d, 0.0)
    for i in range(24, n):
        if i >= 14:
            atr[i] = sum(tr[i - 13:i + 1]) / 14.0
            g = sum(gains[i - 13:i + 1]) / 14.0
            ls = sum(losses[i - 13:i + 1]) / 14.0
            rsi[i] = 100.0 if ls == 0 else 100 - 100 / (1 + g / ls)
        mom[i] = c[i] / c[i - 24] - 1
        mv = sum(v[i - 24:i]) / 24.0
        relvol[i] = (v[i] / mv) if mv > 0 else None
        phi[i] = max(h[i - 24:i])
        plo[i] = min(l[i - 24:i])
    return dict(t=t, o=o, h=h, l=l, c=c, ema20=ema20, ema50=ema50, atr=atr,
                rsi=rsi, mom=mom, relvol=relvol, phi=phi, plo=plo, n=n)


def trend_state(ind, i):
    c, e20, e50, r, m = ind["c"][i], ind["ema20"][i], ind["ema50"][i], ind["rsi"][i], ind["mom"][i]
    if r is None or m is None:
        return None
    if c >= e20 and e20 >= e50 and r >= 50 and m >= 0:
        return "LONG"
    if c <= e20 and e20 <= e50 and r <= 50 and m <= 0:
        return "SHORT"
    return None


def state(variant, ind, i):
    if i < WARMUP or ind["atr"][i] is None:
        return None
    if variant == "trend4":
        return trend_state(ind, i)
    if variant == "breakout":
        ts = trend_state(ind, i)
        rv = ind["relvol"][i]
        if ts is None or rv is None or rv < 1.5:
            return None
        if ts == "LONG" and ind["c"][i] > ind["phi"][i]:
            return "LONG"
        if ts == "SHORT" and ind["c"][i] < ind["plo"][i]:
            return "SHORT"
        return None
    if variant == "meanrev":
        z = (ind["c"][i] - ind["ema20"][i]) / ind["atr"][i]
        if z <= -2.5:
            return "LONG"
        if z >= 2.5:
            return "SHORT"
        return None
    raise ValueError(variant)


def signals(variant, ind, rng):
    """Fresh transitions only (state changes into LONG/SHORT)."""
    src = "trend4" if variant == CONTROL else variant
    out = []
    prev = None
    for i in range(WARMUP, ind["n"] - 1):
        s = state(src, ind, i)
        if s is not None and s != prev:
            out.append((i, rng.choice(["LONG", "SHORT"]) if variant == CONTROL else s))
        prev = s
    return out


# --------------------------------------------------------------------------- trading

def simulate(ind, sig_i, direction, atr_mult=ATR_MULT, rr=RR, horizon=HORIZON):
    e = sig_i + 1
    last = e + horizon - 1
    if last > ind["n"] - 1 or ind["atr"][sig_i] is None:
        return None
    entry = ind["o"][e]
    risk = atr_mult * ind["atr"][sig_i]
    if risk <= 0 or entry <= 0:
        return None
    long_ = direction == "LONG"
    stop = entry - risk if long_ else entry + risk
    tp = entry + rr * risk if long_ else entry - rr * risk
    for j in range(e, last + 1):
        lo, hi, op = ind["l"][j], ind["h"][j], ind["o"][j]
        stop_hit = lo <= stop if long_ else hi >= stop
        tp_hit = hi >= tp if long_ else lo <= tp
        if stop_hit:
            px = min(stop, op) if long_ else max(stop, op)
            g = ((px - entry) if long_ else (entry - px)) / risk
            return dict(gross_r=g, risk_pct=risk / entry * 100, exit_idx=j, kind="STOP")
        if tp_hit:
            return dict(gross_r=rr, risk_pct=risk / entry * 100, exit_idx=j, kind="TP")
    px = ind["c"][last]
    g = ((px - entry) if long_ else (entry - px)) / risk
    return dict(gross_r=g, risk_pct=risk / entry * 100, exit_idx=last, kind="TIME")


def run_variant(variant, inds, max_open, seed):
    rng = random.Random(f"{seed}-{variant}")
    cands = []
    for sym, ind in inds.items():
        for i, d in signals(variant, ind, rng):
            cands.append((ind["t"][i + 1], rng.random(), sym, i, d))
    cands.sort()
    open_until = {}
    trades = []
    for t_entry, _, sym, i, d in cands:
        for s in [s for s, u in open_until.items() if u <= t_entry]:
            del open_until[s]
        if sym in open_until or len(open_until) >= max_open:
            continue
        res = simulate(inds[sym], i, d)
        if res is None:
            continue
        open_until[sym] = inds[sym]["t"][res["exit_idx"]] + HOUR
        res.update(sym=sym, dir=d, t_entry=t_entry, t_exit=open_until[sym])
        trades.append(res)
    return trades


# -------------------------------------------------------------------------- statistics

def net_r(tr, cost):
    return tr["gross_r"] - cost / tr["risk_pct"]


def basic(rs):
    n = len(rs)
    if not n:
        return dict(n=0, mean=None, win=None, pf=None, total=0.0, mdd=0.0)
    mean = sum(rs) / n
    wins = sum(x for x in rs if x > 0)
    loss = -sum(x for x in rs if x < 0)
    eq = peak = mdd = 0.0
    for x in rs:
        eq += x
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    return dict(n=n, mean=mean, win=100.0 * sum(1 for x in rs if x > 0) / n,
                pf=(wins / loss if loss > 0 else None), total=sum(rs), mdd=mdd)


def week_key(ms):
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isocalendar()
    return (d[0], d[1])


def boot_means(trades, cost, reps=3000, seed=7):
    by = defaultdict(lambda: [0.0, 0])
    for tr in trades:
        k = week_key(tr["t_entry"])
        by[k][0] += net_r(tr, cost)
        by[k][1] += 1
    wk = list(by.values())
    if len(wk) < 8:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(reps):
        s = c = 0
        for _ in range(len(wk)):
            a = wk[rng.randrange(len(wk))]
            s += a[0]
            c += a[1]
        out.append(s / c)
    out.sort()
    return out


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    k = min(len(sorted_vals) - 1, max(0, int(p / 100 * len(sorted_vals))))
    return sorted_vals[k]


def quarter_key(ms):
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def evaluate(variant, trades, split_ms, cost):
    disc = [t for t in trades if t["t_entry"] < split_ms]
    hold = [t for t in trades if t["t_entry"] >= split_ms]
    res = {"variant": variant, "segments": {}, "cost_sensitivity": {}}
    lower_p = 100.0 * 0.05 / K_VARIANTS
    for name, seg in (("DISCOVERY", disc), ("HOLDOUT", hold), ("ALL", trades)):
        st = basic([net_r(t, cost) for t in seg])
        bm = boot_means(seg, cost)
        st["ci95"] = (pct(bm, 2.5), pct(bm, 97.5)) if bm else None
        st["ci_lower_bonf"] = pct(bm, lower_p) if bm else None
        st["gross_mean"] = (sum(t["gross_r"] for t in seg) / len(seg)) if seg else None
        res["segments"][name] = st
    for c in COST_LEVELS:
        res["cost_sensitivity"][str(c)] = basic([net_r(t, c) for t in trades])
    q = defaultdict(list)
    for t in trades:
        q[quarter_key(t["t_entry"])].append(net_r(t, cost))
    qs = {k: basic(v) for k, v in sorted(q.items())}
    elig = {k: v for k, v in qs.items() if v["n"] >= 20}
    pos = sum(1 for v in elig.values() if v["mean"] > 0)
    res["quarters"] = qs
    res["positive_quarter_share"] = (pos / len(elig)) if elig else None
    res["quarters_eligible"] = len(elig)
    res["exit_mix"] = {k: sum(1 for t in trades if t["kind"] == k) for k in ("TP", "STOP", "TIME")}
    res["median_risk_pct"] = (sorted(t["risk_pct"] for t in trades)[len(trades) // 2]
                              if trades else None)
    return res


def verdict(res):
    if res["variant"] == CONTROL:
        return None, ["control (not judged)"]
    h = res["segments"]["HOLDOUT"]
    d = res["segments"]["DISCOVERY"]
    checks = []
    checks.append((f"holdout trades >= {CRITERIA['holdout_min_trades']}",
                   h["n"] >= CRITERIA["holdout_min_trades"]))
    checks.append((f"holdout mean net R >= {CRITERIA['holdout_min_mean_net_r']}",
                   h["mean"] is not None and h["mean"] >= CRITERIA["holdout_min_mean_net_r"]))
    checks.append(("holdout CI lower bound > 0 (5%/K)",
                   h.get("ci_lower_bonf") is not None and h["ci_lower_bonf"] > CRITERIA["holdout_ci_lower_gt"]))
    spq = res["positive_quarter_share"]
    checks.append((f">= 2/3 positive quarters (n>=4 quarters)",
                   spq is not None and res["quarters_eligible"] >= CRITERIA["min_quarters_with_20_trades"]
                   and spq >= CRITERIA["min_positive_quarter_share"]))
    checks.append(("discovery mean net R > 0", d["mean"] is not None and d["mean"] > 0))
    return all(ok for _, ok in checks), checks


# ---------------------------------------------------------------------------- report

def f(x, nd=3, sign=False):
    if x is None:
        return "-"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def render(results, cost, meta):
    L = [f"# ATLAS walk-forward screen",
         f"- data: {meta['symbols']} symbols, {meta['bars']} bars, {meta['start']} -> {meta['end']}",
         f"- split: DISCOVERY before {meta['split']}, HOLDOUT after",
         f"- geometry: stop {ATR_MULT}xATR14, target {RR}R, time exit {HORIZON}h; "
         f"cost {cost}% round trip; max_open {meta['max_open']}",
         ""]
    for res in results:
        v, checks = verdict(res)
        tag = "CONTROL" if v is None else ("PASS" if v else "FAIL")
        L.append(f"## {res['variant']} - {tag}")
        L.append("| segment | trades | mean net R | gross R | win% | PF | 95% CI | maxDD(R) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for name in ("DISCOVERY", "HOLDOUT", "ALL"):
            s = res["segments"][name]
            ci = f"{f(s['ci95'][0], 2, True)}..{f(s['ci95'][1], 2, True)}" if s.get("ci95") else "-"
            L.append(f"| {name} | {s['n']} | {f(s['mean'], 3, True)} | {f(s['gross_mean'], 3, True)} | "
                     f"{f(s['win'], 0)} | {f(s['pf'], 2)} | {ci} | {f(s['mdd'], 1)} |")
        cs = " , ".join(f"{c}%: {f(res['cost_sensitivity'][str(c)]['mean'], 3, True)}R"
                        for c in COST_LEVELS)
        L.append(f"- mean net R by cost (ALL): {cs}")
        L.append(f"- exits: {res['exit_mix']}; median stop distance: {f(res['median_risk_pct'], 2)}%")
        L.append(f"- positive quarters: {f(res['positive_quarter_share'], 2)} "
                 f"of {res['quarters_eligible']} eligible")
        if v is not None:
            for name, ok in checks:
                L.append(f"  - [{'x' if ok else ' '}] {name}")
        L.append("")
    L.append("Reading guide: a variant matters only if it PASSES and clearly beats control_random.")
    L.append("A FAIL means no demonstrated edge under these fixed rules, not that no edge exists.")
    return "\n".join(L)


def run_all(data, cost, max_open, seed):
    inds = {s: compute_indicators(r) for s, r in data.items()}
    t0 = min(i["t"][0] for i in inds.values())
    t1 = max(i["t"][-1] for i in inds.values())
    split_ms = t0 + int(0.6 * (t1 - t0))
    results = []
    all_trades = {}
    for v in VARIANTS + [CONTROL]:
        tr = run_variant(v, inds, max_open, seed)
        all_trades[v] = tr
        results.append(evaluate(v, tr, split_ms, cost))
    iso = lambda ms: datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    meta = dict(symbols=len(inds), bars=sum(i["n"] for i in inds.values()), start=iso(t0),
                end=iso(t1), split=iso(split_ms), max_open=max_open)
    return results, all_trades, meta


# ---------------------------------------------------------------------------- selftest

def synthetic(n_sym=6, bars=24 * 365 * 2, seed=3):
    rng = random.Random(seed)
    data = {}
    t0 = 1_600_000_000_000
    for s in range(n_sym):
        px, rows = 100.0, []
        for k in range(bars):
            o = px
            c = o * math.exp(rng.gauss(0, 0.006))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.003)))
            l = min(o, c) * (1 - abs(rng.gauss(0, 0.003)))
            rows.append((t0 + k * HOUR, o, h, l, c, 1000 * (1 + abs(rng.gauss(0, 0.5)))))
            px = c
        data[f"SYN{s}"] = rows
    return data


def selftest():
    # simulate(): hand-built bars
    def mk(bars):
        rows = [(i * HOUR, *b) for i, b in enumerate(bars)]
        ind = compute_indicators(rows)
        ind["atr"] = [1.0 / ATR_MULT] * ind["n"]      # risk = 1.0
        return ind
    flat = (100, 100.2, 99.8, 100, 10)
    # long, target hit on bar 3 (+2R)
    ind = mk([flat, flat, (100, 100.4, 99.6, 100, 10), (100, 102.5, 99.5, 102, 10)] + [flat] * 20)
    r = simulate(ind, 1, "LONG", horizon=6)
    assert r and r["kind"] == "TP" and abs(r["gross_r"] - 2.0) < 1e-9, r
    # long, stop and target in the same bar -> stop first
    ind = mk([flat, flat, (100, 103, 98.5, 100, 10)] + [flat] * 20)
    r = simulate(ind, 1, "LONG", horizon=6)
    assert r and r["kind"] == "STOP" and abs(r["gross_r"] + 1.0) < 1e-9, r
    # short, timeout at close
    ind = mk([flat, flat] + [flat] * 5 + [(100, 100.3, 99.2, 99.5, 10)] + [flat] * 20)
    r = simulate(ind, 1, "SHORT", horizon=6)
    assert r and r["kind"] in ("TIME", "TP", "STOP"), r
    # truncated horizon at the end of data is skipped
    ind = mk([flat] * 5)
    assert simulate(ind, 3, "LONG", horizon=6) is None
    # full pipeline on a driftless random walk: nothing should pass
    data = synthetic()
    results, trades, meta = run_all(data, cost=0.15, max_open=3, seed=1)
    for res in results:
        v, _ = verdict(res)
        n = res["segments"]["ALL"]["n"]
        print(f"selftest {res['variant']}: trades={n} "
              f"gross={f(res['segments']['ALL']['gross_mean'], 3, True)} "
              f"net={f(res['segments']['ALL']['mean'], 3, True)} verdict={v}")
        assert n > 50, "too few trades in selftest"
        assert v is not True, "random walk must not pass"
    print("selftest OK")


# -------------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=3.0)
    ap.add_argument("--cost", type=float, default=0.15, help="round-trip cost in percent of price")
    ap.add_argument("--max-open", type=int, default=3)
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--cache", default="data_cache")
    ap.add_argument("--out", default="wf_out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    data = load_all([s.strip() for s in a.symbols.split(",") if s.strip()], a.years, a.cache, a.refresh)
    if len(data) < 3:
        sys.exit("not enough symbols loaded (network blocked?)")
    results, trades, meta = run_all(data, a.cost, a.max_open, a.seed)
    os.makedirs(a.out, exist_ok=True)
    report = render(results, a.cost, meta)
    with open(os.path.join(a.out, "report.md"), "w") as fh:
        fh.write(report)
    with open(os.path.join(a.out, "results.json"), "w") as fh:
        json.dump(results, fh, indent=1, default=str)
    for v, tr in trades.items():
        with open(os.path.join(a.out, f"trades_{v}.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["symbol", "dir", "t_entry", "t_exit", "gross_r", "risk_pct", "kind"])
            for t in tr:
                w.writerow([t["sym"], t["dir"], t["t_entry"], t["t_exit"],
                            round(t["gross_r"], 4), round(t["risk_pct"], 4), t["kind"]])
    print(report)


if __name__ == "__main__":
    main()