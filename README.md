# ATLAS V1.0 — Crypto Trade Intelligence & Analysis

ATLAS is an **analysis-only** crypto trade intelligence product focused on a canonical **4–12 hour** decision horizon.

Current release candidate: `ATLAS_V1_0_RC1`.

The canonical output is one visible decision only:

- `LONG`
- `SHORT`
- `WAIT`

A qualified LONG or SHORT analysis includes Entry, Stop Loss, Take Profit, R:R, reasons, invalidation, and what must change for the status to change. When qualification, evidence quality, or geometry is not sufficient, the visible decision remains `WAIT`.

## Product status

ATLAS is **READY FOR ANALYSIS** as a technical product.

Forward profitability validation is deliberately separate and remains evidence-driven. A ready product does not imply a validated profitable edge.

See `ATLAS_V1_RELEASE.md` for the release contract and `status/product-readiness-latest.json` for the latest evidence state.

## Product contract

The primary product lane is `CORE_4_12H` and the canonical contract is `analyst_output`.

Short 1–3H and extended 12–24H lanes may exist as research/context, but they are not allowed to override the canonical 4–12H Production decision.

ATLAS remains analysis-only:

- `analysis_only = true`
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
7. AI analysis council
8. On-demand deep analysis
9. Final product quality gate

Research/shadow modules remain isolated from canonical Production authority unless explicitly validated and promoted.

The public decision endpoint is:

`/api/decision/current?symbol=BTCUSDT`

The runtime safety/status endpoint is:

`/api/web-mode`

## Evidence and validation

ATLAS uses separate evidence layers so research cannot silently rewrite Production:

1. Live canonical Production decision
2. Prospective $10K paper evaluation cohort
3. Forward 4h / 8h / 12h settlement
4. Frozen attribution around each canonical observation
5. Retrospective research and shadow diagnostics

The paper portfolio is an **evaluation instrument**, not an auto-trading bot. It records canonical `analyst_output` LONG/SHORT transitions only and evaluates them prospectively using frozen Entry/SL/TP geometry.

No profit, win rate, expectancy, or portfolio value should be treated as established unless it comes from a reproducible committed ledger/report with explicit methodology and sufficient independent forward evidence.

## Deployment

`render.yaml` defines the Render web service. The web process intentionally runs without background research collectors; scheduled evidence collection is handled separately through GitHub Actions so the public analysis runtime stays lightweight and fail-closed.

## Release gates

The repository includes dedicated gates for:

- general ATLAS regression and safety CI
- Product Contract CI
- Final Production Gate
- Render Reliability Gate
- ATLAS V1.0 Release Gate

The V1.0 release gate verifies the live canonical runtime and all eight supported analyzers before the product is considered ready for analysis.

## Engineering rules

- Do not weaken thresholds to reduce `WAIT` frequency.
- Do not describe a UI panel as Production integration unless its data path is verified.
- Major changes require regression coverage.
- Never claim a change is complete before code, tests, and required Production checks pass.
- Preserve one canonical visible decision authority.
- Keep operational readiness separate from forward profitability validation.

## Status

**Product:** READY FOR ANALYSIS  
**Canonical horizon:** 4–12H  
**Canonical decisions:** LONG / SHORT / WAIT  
**Live execution:** OFF  
**Forward profitability validation:** EVIDENCE PENDING until the preregistered sample gate is satisfied.
