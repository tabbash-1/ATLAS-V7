# ATLAS V7 — Crypto Trade Intelligence & Analysis

ATLAS is an analysis-only crypto trade intelligence product focused on a **4–12 hour** decision horizon.

It does **not** auto-trade real money. The canonical output is one visible decision only:

- `LONG`
- `SHORT`
- `WAIT`

A qualified analysis includes Entry, Stop Loss, Take Profit targets, R:R, decision reasons, trigger/permission state, and invalidation context. When qualification or geometry is not sufficient, the visible decision remains `WAIT`.

## Product contract

The primary product lane is `CORE_4_12H`.

Short 1–3H and extended 12–24H lanes may exist as research/context, but they are not allowed to override the canonical 4–12H Production decision.

ATLAS remains analysis-only:

- `live_execution = false`
- no exchange order routing
- no automatic real-money position management
- manual user execution remains outside ATLAS

See `ATLAS_STARTUP_CONSTITUTION.md` for the non-negotiable product and evidence rules.

## Production decision path

The web runtime installs the current Production analysis stack through `cloud_web_only.py`, including:

1. Production signal scoring
2. Continuation scoring
3. Canonical decision API
4. Decision engine
5. 4–12H product/horizon overlay
6. Risk and geometry assessment
7. AI trade council
8. On-demand deep analysis

Research/shadow modules remain isolated from canonical Production authority unless explicitly validated and promoted.

The public decision endpoint is:

`/api/decision/current?symbol=BTCUSDT`

The runtime safety/status endpoint is:

`/api/web-mode`

## Evidence and validation

ATLAS uses separate evidence layers so research cannot silently rewrite Production:

1. Live canonical Production decision
2. Prospective $10K paper evaluation cohort
3. Forward/offline path settlement
4. Retrospective research and shadow diagnostics

The paper portfolio is an **evaluation instrument**, not an auto-trading bot. It records only canonical `TRADE READY` observations and evaluates them prospectively, including 4h / 8h / 12h product-window evidence.

No profit, win rate, expectancy, or portfolio value should be treated as established unless it comes from a reproducible committed ledger/report with explicit methodology.

## Deployment

`render.yaml` defines the Render web service. The web process intentionally runs without background collectors; scheduled research is handled separately through GitHub Actions so the public analysis runtime stays lightweight and fail-closed.

## Engineering rules

- Do not weaken thresholds to reduce `WAIT` frequency.
- Do not describe a UI panel as Production integration unless its data path is verified.
- Major changes require regression coverage.
- Never claim a change is complete before code, tests, and required Production checks pass.
- Preserve one canonical visible decision authority.

## Status

ATLAS V7 is under active production hardening. The repository contains the current Production analysis path, forward/paper validation tooling, reliability checks, and research layers. Startup readiness is judged by verified runtime behavior and evidence quality, not by feature count or UI appearance alone.
