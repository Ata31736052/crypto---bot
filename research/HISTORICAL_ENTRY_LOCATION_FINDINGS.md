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
