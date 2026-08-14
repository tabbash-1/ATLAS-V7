# ATLAS V5 Anomaly / Early Warning — Alpha 12

Research-only. Live execution disabled.

## Added
- Volume spike / elevation detection using rolling z-scores.
- Candle range expansion and return shock detection.
- OI expansion / shock detection.
- Aggressive taker-buy / taker-sell detection.
- Order-book imbalance warnings.
- Extreme funding and squeeze-risk flags.
- Combined Anomaly Score with NORMAL / WATCH / ELEVATED / HOT levels.
- Directional bias: BULLISH / BEARISH / MIXED / NEUTRAL.
- HOT WATCH priority inside Opportunity Scanner.

## Guardrail
Anomaly score does NOT increase the Final Opportunity Score.
It only influences which candidates receive deeper enrichment earlier.
The setup must still pass S/R, volume, futures, historical, R:R and portfolio-risk gates.

## Research goal
Measure whether abnormal flow/volatility conditions appear before validated high-quality opportunities often enough to improve scan efficiency and expectancy.
