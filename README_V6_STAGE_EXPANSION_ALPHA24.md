# ATLAS V6 Stage Expansion & Rollback — Alpha 24

Research-only. Live execution disabled.

## Purpose
Expand a successful Shadow Canary gradually instead of jumping from 15% to full exposure.

## Stages
- 15% Canary / 85% Control
- 30% Canary / 70% Control
- 50% Canary / 50% Control

Each forward observation freezes the active stage at entry.

## Independent pass criteria
Stage 15:
- Canary N >= 25
- Control N >= 75

Stage 30:
- Canary N >= 35
- Control N >= 60

Stage 50:
- Canary N >= 50
- Control N >= 50

Every stage also requires:
- paired average improvement >= 0.02 percentage points
- paired risk-adjusted improvement >= 0.03
- paired drawdown worsening <= 0.10 proxy units

## Transition logic
- PASS -> expand to next Shadow stage
- FAIL -> rollback one stage
- INCONCLUSIVE -> hold
- COLLECTING -> hold
- EDGE_RISK -> automatic Shadow rollback one stage
- DEGRADED Data Quality -> automatic Shadow rollback one stage
- Stage 50 PASS -> hold at maximum Shadow stage

The Cloud Forward Worker applies this transition check after each research cycle.

## State persistence
`canary_stage_state.json` stores:
- active stage
- highest passed stage
- status
- transition history
- timestamps

Historical observations retain their original stage and are never relabeled.

## Critical guardrail
Automatic expansion/rollback affects Shadow assignment only.
There is still:
- no live capital
- no exchange orders
- no automatic activation into Portfolio Risk
- no Final Score changes

## APIs
- GET `/api/canary/stages`
- GET `/api/canary/stages/apply`
