# ATLAS Startup Constitution

ATLAS is a real startup-grade crypto trade intelligence product, not a demo and not a conversational experiment.

## Product mission
ATLAS analyzes crypto opportunities for a 4–12 hour holding horizon and exposes one canonical visible decision only: `LONG`, `SHORT`, or `WAIT`, with Entry, Stop Loss, Take Profit targets, R:R, reasons, trigger, and invalidation.

## Non-negotiable rules
1. Never claim a feature exists or works until it is verified in code and, when applicable, on the live Production deployment.
2. When a defect is found: identify root cause, repair code, add or update regression coverage, deploy/commit, verify Production, then report the result.
3. Do not stop at recommendations when the repository/tooling permits the fix to be implemented directly.
4. Never change decision rules, thresholds, datasets, or labels merely to make performance look better.
5. Never claim profit, P&L, win rate, expectancy, or portfolio value unless it comes from a reproducible committed ledger/report with explicit methodology.
6. Preserve prior validated work. Do not rebuild ATLAS from scratch without a documented technical reason.
7. Research/shadow layers cannot override the canonical Production decision.
8. ATLAS does not auto-trade real money. `live_execution` remains false. A trade may become `TRADE READY`, but the user executes manually outside ATLAS.
9. Major changes require regression tests and must preserve single-decision authority.
10. Do not use the word “done” for a change until the implementation and its required tests/Production checks pass.

## Canonical decision contract
A visible `LONG` or `SHORT` is allowed only when the canonical Production contract says the trade is qualified, geometry is valid, and explicit trigger/permission is present. Otherwise the visible action is `WAIT`.

`geometry_ready` means Entry/SL/TP geometry is valid. It is not an entry instruction.

`TRADE READY` means the canonical plan is qualified and explicitly permitted for manual execution. It does not mean an order was sent to an exchange.

## $10K Paper Portfolio contract
ATLAS maintains a prospective paper portfolio beginning at exactly `$10,000`. It records only canonical `TRADE READY` events after the immutable portfolio cohort start. It does not retroactively select historical winners or backfill old trades.

The paper portfolio must provide an append-verifiable trade record, frozen decision-time geometry, risk sizing, R multiple, dollar P&L, equity after each settled trade, peak equity, drawdown, win rate, and LONG/SHORT attribution. Missing market data is never filled with zero and ambiguous SL/TP paths are never guessed.

The portfolio is paper-only and has no Production decision authority.

## Evidence hierarchy
1. Live canonical Production decision and its verified contract.
2. Immutable prospective paper/validation cohorts.
3. Reproducible offline path settlement and forward evaluation.
4. Retrospective research and shadow diagnostics.

Lower levels may inform future product changes only after explicit validation; they do not silently alter Production.
