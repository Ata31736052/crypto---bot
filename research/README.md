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
python -m unittest tests/test_closed_candle_timing_audit.py tests/test_entry_exit_location_audit.py -v
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

## Historical support/resistance and trade-location audit

The separate `research/entry_exit_location_audit.py` module evaluates proposed entry
location and trade geometry; it is **not connected to the live bot**. It uses only
confirmed swing highs/lows from candles before the signal candle, excluding the
signal candle itself from level detection.

For BUY setups it can reject entries too close to overhead historical resistance,
targets that would sit through resistance, or structurally excessive stop distances.
For SELL setups it checks the mirrored support/target geometry. It returns explicit
rejection reasons, obstacle distance in ATR units, structural stop, TP1/TP2, and R:R.
Defaults require at least 1.5 ATR of room to the nearest obstacle, use a 0.25 ATR
buffer, and retain the configured 1.8/2.4 R:R targets. These are research defaults
to evaluate, not a validated profitable configuration.

The test suite includes a BUY near resistance, signal-candle exclusion, targets
blocked by resistance, SELL near support, and invalid-input cases. Before any
production integration, replay this gate against historical signals and compare
candidate acceptance, net returns, MFE/MAE, and TP/SL first-event rates on a
chronological holdout. Do not relax the existing production filters just to
increase signal count.

## Replay the repository's recorded signals

`research/replay_historical_entry_locations.py` reads the existing
`signals_history.json`, downloads public Binance Spot 1-hour candles for the
recorded symbols, and writes `historical_entry_location_replay.csv`. On a pull
request, the research workflow runs this in research-only mode and uploads the
CSV as an artifact. It does not run the live scan or send Telegram messages.

For each recorded signal, the replay:
- Uses only candles whose close time is at or before the recorded signal timestamp
  to derive ATR and historical swing levels; an in-progress candle is excluded.
- Reports nearest historical resistance/support, obstacle distance in ATR,
  structural stop/targets, and explicit location-gate rejection reasons.
- Measures forward close returns, MFE and MAE at 1, 4, 8, 12, 24 and 48 hours
  where Binance candle coverage is complete.
- Reports data gaps/API failures rather than treating missing candles as a pass.

**Important data limitation:** the existing history JSON does not store the
engine's setup label for every row. The replay therefore uses reason-text heuristics
and labels results `TREND_HEURISTIC` or `BOTTOM_HUNTER_HEURISTIC`; these labels
are approximate, not authoritative. The replay is descriptive research, not a
validated counterfactual backtest. It does not yet prove how the live engine would
have behaved if the gate had been enabled. Do not wire this gate into production
until the artifact has adequate coverage and results are reviewed on a chronological
holdout.
