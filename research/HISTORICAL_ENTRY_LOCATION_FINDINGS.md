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


## Stage 1: Was the signal already late in the prior move?

A new research-only replay extension records the move's state at each historical signal, independently from the support/resistance gate. It adds:

- Prior close-to-close returns over 12h, 24h, and 48h before the signal.
- Entry position inside the trailing 24h, 48h, and 72h high-low ranges.
- Directional progress through each range (for BUY, low-to-high; for SELL, high-to-low).
- Distance from entry to the directionally relevant range obstacle in ATR units.
- Descriptive early/middle/late thirds of the trailing 72h directional range, then gross 8h/24h/48h outcomes and MFE/MAE for each group.

**No-lookahead rule:** every feature above uses only hourly candles whose close time is at or before the recorded signal timestamp. The signal candle is not used to calculate its prior range or returns. Setup names remain reason-text heuristics, not authoritative engine labels. These thirds are descriptive buckets, not proposed production thresholds.

The updated pull-request workflow is running the compile, regression, and historical replay checks. Results should be interpreted only after that run completes; this extension is not wired into the production signal engine and does not change Telegram behavior.


### Stage 1 results — chronological holdout, direction-adjusted outcomes

Latest successful research replay: [workflow run #265](https://github.com/Ata31736052/crypto---bot/actions/runs/38260052722)  
[Download replay CSV artifacts](https://github.com/Ata31736052/crypto---bot/actions/runs/38260052722/artifacts/11751573461)

The replay now calculates both pre-signal returns and forward returns in the signal direction (including SELL events). The holdout still contains 94 Trend-heuristic and 30 Bottom-Hunter-heuristic events.

| Holdout group | 72h directional range stage | Events | Mean directional move in prior 24h | Mean 72h range progress | Mean next 24h return | Positive next 24h |
|---|---|---:|---:|---:|---:|---:|
| Trend | Middle third | 39 | +2.61% | 51.7% | +0.11% | 53.8% |
| Trend | Late third | 55 | +5.78% | 79.0% | -0.99% | 27.3% |
| Bottom Hunter | Early third | 15 | -0.46% | 25.2% | +2.96% | 93.3% |
| Bottom Hunter | Middle third | 11 | -1.44% | 46.2% | +1.64% | 81.8% |
| Bottom Hunter | Late third | 4 | +0.65% | 91.1% | +0.14% | 50.0% |

**Main finding:** the concern about late Trend entries is supported by this holdout sample. 55 of 94 Trend events (58.5%) landed in the late third of the prior 72h directional range. Their average prior 24h move was +5.78%, yet their next 24h directional return averaged -0.99%, with only 27.3% positive. The middle-third group had a much smaller prior move (+2.61%) and nearly flat next-24h average return (+0.11%). This is a useful diagnostic signal, not proof that a new gate will be profitable; market regimes, fees/slippage, and the small historical window still matter.

For Bottom Hunter, the early-third group looked materially better than the late-third group, but the late-third group has only four events. Do not tune or deploy a cutoff based on that tiny subgroup. The engine labels are inferred from historical reason text, not guaranteed ground truth.

**Decision:** do not lower global score/ADX/volume gates and do not integrate a blanket location gate. The next research step should evaluate a *Trend-only late-move rejection or re-entry/wait rule* against a chronological holdout with directional 8h/24h/48h returns, MFE/MAE, and explicit fee/slippage assumptions. Keep Bottom Hunter separate. No production files or live Telegram behavior were changed.
