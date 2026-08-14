# ATLAS V5 Final Opportunity Ranking — Alpha 6

Research-only. Live execution disabled.

## Two-stage scanner
1. Broad scan: market structure, confluence, volume, market regime, BTC-relative strength and room to next obstacle.
2. Enrich only the top 3 candidates with collector Futures data, observed order-book liquidity and sample-size-weighted Pattern Memory.
3. Re-rank using Final Opportunity Score.

## Guardrails
- Final score is not a probability.
- Missing enrichment stays neutral rather than being treated as positive.
- Historical evidence weight increases only with sample size.
- Observed order-book liquidity is separated from estimated liquidation pressure.
- A blocked/no-direction setup cannot become a candidate solely because of Futures or relative strength.
- Live execution remains disabled.

## Next planned layer
News/Event Intelligence in shadow mode, followed by forward validation of whether event context improves expectancy.
