# Historical entry-location replay findings

Date of replay: 2026-10-12  
Workflow run: [#249](https://github.com/Ata31736052/crypto---bot/actions/runs/38257519875)  
Artifact: [download replay CSVs](https://github.com/Ata31736052/crypto---bot/actions/runs/38257519875/artifacts/11751865175)

## Coverage and method

- Source: repository `signals_history.json` (437 records).
- Repeated same-symbol/side/candle records removed: 24; unique events evaluated: 413.
- Binance Spot 1-hour candle sets fetched: 67/67 symbols.
- Every level/ATR calculation used only candles whose close time was at or before the signal timestamp.
- Forward outcomes use the recorded signal entry and later closed candles. Returns are gross, with no fee/slippage adjustment.
- The history does not store authoritative setup labels; `TREND_HEURISTIC` and `BOTTOM_HUNTER_HEURISTIC` are inferred from reason text.

## Results for the current strict location gate

| Heuristic group | Events | Rejected | 8h average return (rejected / accepted) | 24h average return (rejected / accepted) | 48h average return (rejected / accepted) |
|---|---:|---:|---:|---:|---:|
| Trend | 313 | 296 (94.6%) | -0.454% / +0.582% | -0.498% / +0.536% | +0.801% / +2.054% |
| Bottom Hunter | 100 | 95 (95.0%) | +0.101% / -0.454% | -0.559% / -1.299% | +1.030% / -0.461% |

Accepted sample sizes were only 17 Trend and 5 Bottom Hunter events. These numbers are exploratory, not evidence of a reliable edge. The 95% rejection rate is too high to adopt this gate as-is; it risks suppressing nearly all candidates. Trend's accepted group is encouraging but very small, while the Bottom Hunter accepted group did not improve in this sample.

## Decision

**Do not connect this strict gate to the live signal engine yet.** Keep it research-only. The next comparison should test a small, pre-declared set of location policies on the same deduplicated events, including a separate Bottom Hunter policy, and compare chronological holdout results, target obstruction, MFE/MAE, and sample retention. Do not select thresholds just because they produce more signals or a better in-sample average.

The existing production code and live Telegram behavior were not changed by this replay.


## Chronological holdout sensitivity check

The replay was extended with a chronological holdout beginning at
`2026-10-03T00:05:47Z`, after sorting/deduplicating recorded signal timestamps.
The final holdout contains 94 Trend-heuristic events and 30 Bottom-Hunter-heuristic
events. The comparison below is exploratory; candidate policies were evaluated
without changing the live engine.

| Holdout group | Candidate policy | Accepted | Accepted 8h avg | Accepted 24h avg | Accepted 48h avg |
|---|---|---:|---:|---:|---:|
| Trend | Strict: 1.5 ATR and both targets clear | 2/94 (2.1%) | -0.730% | -0.851% | -2.180% |
| Trend | TP1 clear, 1.0 ATR room; TP2 must be capped if obstructed | 3/94 (3.2%) | -1.329% | -1.370% | -1.213% |
| Trend | TP1 clear, 0.5 ATR room; TP2 must be capped if obstructed | 3/94 (3.2%) | -1.329% | -1.370% | -1.213% |
| Bottom Hunter | Strict: 1.5 ATR and both targets clear | 2/30 (6.7%) | -0.651% | -0.028% | -0.244% |
| Bottom Hunter | TP1 clear, 1.0 ATR room; TP2 must be capped if obstructed | 4/30 (13.3%) | +0.132% | +1.069% | +3.676% |
| Bottom Hunter | TP1 clear, 0.5 ATR room; TP2 must be capped if obstructed | 4/30 (13.3%) | +0.132% | +1.069% | +3.676% |

The candidate variants increase sample retention only modestly. Their accepted holdout
groups are still tiny (3 Trend and 4 Bottom Hunter records), so their apparent returns
are highly unstable and not sufficient to justify live integration. The 0.5 and
1.0 ATR candidates accepted the same holdout records, suggesting these cutoffs did
not meaningfully distinguish cases in this sample.

The TP1-only candidates deliberately ignore a blocked TP2 for the *entry-location
sensitivity comparison only*. Any later implementation would have to cap TP2 before
the historical obstacle and recompute actual reward/risk; this replay does not model
that revised exit plan. Do not treat these numbers as strategy P&L.
