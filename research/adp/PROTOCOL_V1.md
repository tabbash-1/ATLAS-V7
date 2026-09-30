# ATLAS Direction Predictor (ADP) — Research Protocol V1

Status: RESEARCH ONLY. This track cannot alter Production, FINAL_TRADE_GATE, threshold 68, execution, or portfolio accounting.

## Objective
Predict forward market direction at 4h, 8h, and 12h from information available at signal time.

Labels per horizon:
- UP: forward return > locked neutral band
- DOWN: forward return < -locked neutral band
- NEUTRAL: otherwise

The neutral band and all feature definitions must be frozen before holdout evaluation.

## Candidate feature families
1. Price structure: HH/HL vs LH/LL, distance from prior swing/range, breakout/retest state.
2. Momentum persistence: multi-window returns and slope/acceleration, not raw ATLAS score.
3. Volatility state: ATR-normalized displacement, compression/expansion.
4. Participation: relative volume and volume expansion.
5. Relative strength / market context: asset vs BTC plus BTC directional context.

## Anti-overfit protocol
- Strict chronological split: development -> validation -> untouched test -> forward.
- No random train/test split.
- No feature/threshold tuning on untouched test.
- No future bars in features; all joins are point-in-time.
- Report every evaluated symbol and period; no cherry-picking.
- Keep LONG/SHORT and 4h/8h/12h metrics separate.
- Baselines: always-UP, always-DOWN, previous-return momentum, simple EMA trend.
- Primary target is directional generalization, not historical PnL.
- Trading evaluation is secondary and includes fees/slippage.

## Promotion rule
No Production integration. Pine/TradingView product work begins only after an untouched test shows repeatable directional edge and a subsequent forward cohort confirms it.

## Required report
For every candidate:
- sample count
- balanced accuracy / per-class precision and recall
- UP and DOWN precision
- confusion matrix
- 4h / 8h / 12h performance
- symbol and regime breakdown
- calibration by confidence bucket
- cost-adjusted trade expectancy when mapped to BUY/SELL
- comparison with baselines
- explicit discovery vs validation vs untouched test

## CI validity guard
A research run is valid only when the experiment exits successfully and emits a non-empty `ADP_RESULT`; green CI without that payload is invalid evidence.

## V2 candidate scan
V2 candidates are selected using development and validation only. Untouched-test outcomes must remain sealed until one candidate is frozen.
