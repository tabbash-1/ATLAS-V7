# ATLAS V6 Trader Playbook Research — Alpha 16

Research-only. Live execution disabled.

## Purpose
Translate professional trading logic into explicit scenario labels that can be forward-tested rather than blindly copied.

## Initial Playbooks
- BREAKOUT_CONTINUATION_LONG
- BREAKDOWN_CONTINUATION_SHORT
- TREND_PULLBACK_LONG
- TREND_PULLBACK_SHORT
- LEVERAGE_TRAP_LONG_RISK
- LEVERAGE_TRAP_SHORT_RISK
- SHORT_SQUEEZE_REVERSAL_WATCH
- LONG_SQUEEZE_REVERSAL_WATCH
- RANGE_RESISTANCE_REJECTION_WATCH
- RANGE_SUPPORT_REJECTION_WATCH

## Inputs
Playbooks use combinations of:
- Market regime
- S/R strength and distance
- Breakout / breakdown quality
- Relative and quality volume
- Futures bias, funding, OI, taker ratio and book imbalance
- Squeeze state
- Relative strength
- Anomaly score
- Trade-plan R:R

## Important behavior
A Playbook is a hypothesis label, not a new signal.
It does not increase Final Opportunity or Master Conviction scores.

## Forward research
When an Alpha 15 forward observation is frozen, ATLAS also freezes:
- primary playbook
- playbook score
- all matched playbooks

`/api/playbooks/stats` then measures 24h directional:
- N
- hit rate
- average return
- profit-factor proxy
- max-drawdown proxy

Early read: >=20 observations per playbook.
Stronger read: >=50 observations per playbook.

## Management logic
Each playbook includes:
- why it matched
- preferred management behavior
- conditions to avoid

Examples:
- Breakout continuation prefers confirmation/retest rather than chasing.
- Leverage trap explicitly warns against chasing crowded leverage into nearby resistance/support.
- Squeeze playbooks require structural confirmation; crowding alone is never treated as an entry.

## Guardrail
No playbook can influence capital allocation until it survives forward validation.
