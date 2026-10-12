# Full historical replay run

Research-only execution notes for the historical signal replay workflow.

- Keep production `main` unchanged; do not merge this research branch as a trading-rule change.
- Workflow: `.github/workflows/historical-signal-replay.yml`
- Default full run: 180 evaluation days, 260 warm-up days, fixed Binance Spot cohort BTC, ETH, BNB, SOL, XRP, ADA, DOGE, LTC, LINK, AVAX.
- Assumed round-trip cost: 0.4 percentage points.
- Expected output: uploaded workflow artifact containing replay summary and per-signal outcomes.
- A successful compile/smoke test is not a performance result; review the full replay metrics before considering any strategy changes.
