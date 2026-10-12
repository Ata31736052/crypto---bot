# Research-only closed-candle audit

This directory is deliberately separate from the signal-generation engine. It does
not create recommendations, send Telegram messages, or place orders.

## Required inputs

Create two UTF-8 CSV files outside the repository:

**signals.csv**
`symbol,setup,timestamp`

Example setup labels: `TREND` and `BOTTOM_HUNTER`. Timestamps must be timezone-aware
ISO-8601 in UTC, for example `2026-01-01T12:00:00Z`.

**candles.csv**
`symbol,timestamp,open,high,low,close`

Use fully closed hourly candles, with each timestamp consistently labeling the
candle close. Candle timestamps must be one hour apart; missing hourly candles
invalidate later horizons. Do not include the still-forming candle. The signal
timestamp must align with a closed hourly candle and its close is used as the
reference entry. Outcomes start with the next hourly candle, so the signal candle
cannot inflate forward return, MFE, or MAE.

## Run

```bash
python -m unittest tests/test_closed_candle_timing_audit.py -v
python research/closed_candle_timing_audit.py \
  --signals signals.csv \
  --candles candles.csv \
  --horizons 1,4,8,12,24,48 \
  --fee-bps-per-side 10 \
  --slippage-bps-per-side 5 \
  --out outcomes.csv \
  --summary-out summary.csv
```

The fee and slippage values are assumptions for sensitivity testing, not a claim
about actual exchange fees or fills. Replace them with documented assumptions
when available. Results are separated by setup and horizon and include net/gross
returns, net win rate, MFE, MAE, and time to recover to entry after an adverse
hourly close. Recovery is reported only when it occurs within that horizon.

## Interpretation limits

- This is an outcome evaluator, not a historical signal generator. It cannot
  establish performance unless supplied with a complete, timestamped export of
  actual historical signals and matching Binance candles.
- A result from a single horizon or a small sample is not proof of profitability.
  Use a chronological holdout and report the sample count and missing coverage.
- This does not yet migrate the bot's live signal engine to Daily + 4H primary
  with 1H confirmation. That architecture change must be independently audited
  for every hard-coded timeframe, closed-candle boundary, risk/stop geometry,
  score gate, BTC regime input, and diagnostic label before any deployment.
- The main branch is intentionally unchanged. The workflow in this research
  branch has `DRY_RUN=1` as a safety lock.
