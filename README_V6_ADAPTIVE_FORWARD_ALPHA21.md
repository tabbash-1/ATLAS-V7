# ATLAS V6 Adaptive vs Fixed Forward Test — Alpha 21

Research-only. Live execution disabled.

## Purpose
Test whether adaptive sizing improves performance compared with fixed sizing on the same future observations.

## Frozen sizing
At forward-observation time ATLAS freezes:
- fixed risk %
- adaptive shadow multiplier
- adaptive shadow risk %

The adaptive multiplier is computed from the evidence available at that moment. Later learning cannot rewrite old sizing decisions.

## Comparison
For matured 24h observations ATLAS compares:
- average weighted directional return
- total weighted return proxy
- max drawdown proxy
- profit-factor proxy
- simple risk-adjusted return / drawdown proxy

Preliminary verdicts:
- ADAPTIVE_LEADING_SHADOW
- FIXED_LEADING
- NO_CLEAR_EDGE
- COLLECTING

A verdict requires at least 40 usable matured observations.

## Guardrail
Even ADAPTIVE_LEADING_SHADOW does not change Portfolio Risk or real/research execution sizing in Alpha 21.
The adaptive path remains a prospective shadow experiment.
