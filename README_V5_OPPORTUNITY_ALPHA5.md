# ATLAS V5 Opportunity Scanner — Alpha 5

Adds a cross-sectional crypto opportunity layer on top of the existing ATLAS engines.

## New research components
- Market Regime fit using existing V4 regime detector (trend/range + volatility).
- Relative Strength vs BTC over 12 / 48 / 120 candles.
- Direction-aware room-to-obstacle score using dynamic S/R.
- Opportunity score combining base signal, confluence, regime fit, relative strength, volume, S/R room and breakout/breakdown quality.
- Crypto universe ranking: BTC, ETH, SOL, XRP, BNB, DOGE, ZEC.

## Important
The Opportunity Score is a transparent research ranking, not a probability and not a profitability claim. It does not yet include per-asset historical Pattern Memory, live Futures/Liquidity enrichment for every scanned asset, or News/Event Intelligence. Those remain subsequent validation layers.
