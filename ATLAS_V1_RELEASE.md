# ATLAS V1.0 Release Candidate

Release: `ATLAS_V1_0_RC1`

## Product state

ATLAS is ready to be used as an **analysis-only crypto trade intelligence product** for a canonical **4–12 hour** horizon.

The only canonical product decision is:

- `LONG`
- `SHORT`
- `WAIT`

When a LONG or SHORT analysis is ready, ATLAS provides Entry, Stop Loss, Take Profit, R:R, reasons, invalidation, and status-change conditions. When the setup or geometry is insufficient, the canonical result remains WAIT.

## Non-negotiable safety contract

- Canonical contract: `analyst_output`
- Canonical lane: `CORE_4_12H`
- `analysis_only = true`
- `live_execution = false`
- no order routing
- no autonomous position management
- Production score threshold is not changed by the release layer
- research/shadow evidence cannot override the canonical Production decision

## What READY means

`READY_FOR_ANALYSIS` means the product architecture, canonical decision contract, runtime, analyzer outputs, safety invariants, and Production checks are operational.

It does **not** mean that profitability has been validated.

Forward validation continues independently using frozen canonical LONG/SHORT observations at 4h / 8h / 12h. The preregistered evidence gate remains separate and cannot be bypassed by a release label.

## Validation state at RC1

The committed readiness snapshot currently reports `TECHNICALLY_READY_EVIDENCE_PENDING`.

Therefore:

- technical operation may be claimed
- forward edge validation may not be claimed
- profitability may not be claimed

This separation is intentional: ATLAS can be a finished usable analyzer while prospective evidence continues to accumulate.

## Final release acceptance

The `ATLAS V1.0 Release Gate` verifies:

1. committed technical readiness
2. live Render canonical runtime
3. all eight supported analyzers
4. analyst_output / CORE_4_12H contract
5. LONG / SHORT / WAIT-only canonical semantics
6. analysis-only and no-live-execution invariants
7. unchanged Production threshold semantics

A release is accepted only when that gate passes.
