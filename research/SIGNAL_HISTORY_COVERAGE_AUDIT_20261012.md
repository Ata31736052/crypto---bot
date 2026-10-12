# Signal-history coverage audit (research only)

Audit date: 2026-10-12  
Source: `signals_history.json` on branch `research/closed-candle-architecture-audit-20261012`  
Scope: metadata/coverage audit only; no signal generation, Telegram, or order placement.

## Measured coverage

- Rows in the file: **437**.
- Timestamp range: **2026-10-01 17:25:10 UTC** through **2026-10-04 05:23:35 UTC**.
- Elapsed span: **2.50 days**, across **4 calendar dates** (Oct 1–4) and **1 calendar month**.
- Distinct symbols represented: **67**.
- Side counts: **358 BUY**, **79 SELL**.
- Required signal fields (timestamp, symbol, side, entry, stop loss, TP1): **0 rows missing at least one field**.
- Exact `timestamp + symbol + side` duplicate keys: **0**.
- Repeated `symbol + candle_time + side` keys: **23 keys / 24 extra rows**. These may be repeat alerts on the same hourly candle and should not automatically be counted as independent trades.
- The current replay classifies setup heuristically from free-text reasons. It is not a canonical engine label.

## What this means

The available signal history is **not a longer independent out-of-sample dataset**. It covers only 2.5 days, so it cannot reliably represent bullish, bearish, and sideways regimes or establish that an entry rule generalizes. The 24 repeat rows at the same symbol/candle/side also mean that event count and independent-trade count are not interchangeable.

The previous first-barrier replay remains a useful diagnostic of the recorded events, but it does not replace a historical signal-generation backtest. Replaying current recorded signals against older prices would be invalid; it would use signals that were not actually generated at those old timestamps.

## Next valid experiment

1. Build a **research-only historical signal generator** that runs the exact candidate engine on Binance Spot candles as they were available at each historical decision time. Do not use future candles, current universe membership, or current regime data for past decisions.
2. Generate a timestamped signal ledger on historical periods that include separate uptrend, downtrend, and sideways regimes.
3. Split chronologically into development and untouched holdout periods; deduplicate repeat alerts by symbol + decision candle + side, while preserving a separate alert-count metric.
4. Evaluate recorded entry, SL, TP1/TP2, spread/fees/slippage sensitivity, and conservative same-candle barrier ordering. Report sample size and coverage gaps by regime and setup.
5. Keep production logic unchanged until a candidate passes the untouched holdout and has adequate sample coverage.

## Decision

**Do not promote the late-third exclusion or pullback-reclaim policy to production based on the current history.** The existing dataset is too short, and the tested pullback-reclaim variant performed worse in the earlier replay. The next implementation task is a no-Telegram, no-live-scan historical signal generator, not another threshold tweak.
