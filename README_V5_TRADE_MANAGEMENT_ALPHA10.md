# ATLAS V5 Trade Management — Alpha 10

Research-only. Live execution disabled.

## Added
- Entry zone from current price + ATR context.
- Structural invalidation using nearby support/resistance when reasonable.
- ATR fallback stop and 3 ATR risk cap.
- TP1/TP2 placed before S/R and observed liquidity obstacles.
- R:R quality gate.
- Strong obstacle inside 1R caution.
- Post-TP1 management template: partial exit, breakeven/structure stop, 1.2 ATR trailing.
- Final Opportunity Scanner now shows R:R2 and an Execution decision that can downgrade a high signal when trade geometry is poor.

## Exit Research Lab
Compares:
1. Fixed: 1.5 ATR stop + 2R target.
2. S/R-managed: partial TP1, breakeven, TP2, trailing.

Uses sequential historical signal snapshots and conservative same-bar stop priority.
A configurable round-trip cost proxy in basis points is included.

## Guardrails
- Trade plan quality does not increase the alpha score.
- Poor R:R or blocked S/R can downgrade execution to WATCH / NO_TRADE.
- Exit-management rules are not considered superior until validated.
- Live execution remains disabled.

## Current test lesson
On a synthetic sample, S/R-managed exits were roughly similar to fixed ATR exits and did not automatically outperform. This is intentional evidence that the Exit Lab must decide which management style is retained.
