# ATLAS V5.1 Master Conviction Alpha 3

Research-only scoring layer. It does not execute trades.

## Added
- Master Conviction score 0-100.
- Separates signal quality from blockers/cautions/confirmations.
- Sample-size-weighted Pattern Memory: <10 cases = zero historical weight; weight rises progressively with evidence.
- Futures context is directional and optional; missing data remains neutral.
- Strong S/R gate remains a hard blocker.
- Decisions: NO_TRADE, WATCH, LONG_WATCH, SHORT_WATCH, LONG_CANDIDATE, SHORT_CANDIDATE.
- Capital status remains RESEARCH_ONLY_NOT_VALIDATED until adequate matured evidence exists; even then forward validation is required.

## Current research weights
Base 22%, confluence 23%, volume 14%, breakout/breakdown 11%, S/R gate 10%, futures up to 12%, historical up to 18%. Missing evidence weight is filled with neutral 50, not optimism.

These are starting research weights, not validated production weights. Future walk-forward calibration should replace them.
