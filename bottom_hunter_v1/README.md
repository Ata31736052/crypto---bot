# Bottom Hunter v1 — isolated prototype

This is a clean, isolated prototype. It does not replace or modify the existing scanner and does not place orders.

## Design goals
- Hunt an early rebound after a recent decline.
- Use only closed Binance Spot candles.
- Keep the first version deliberately simple: recent decline + bullish close above the previous candle's high + basic volume sanity check.
- No RSI, ADX, EMA stack, multi-timeframe confirmation, complex score, or auto-trading.
- Produce an entry reference, structural stop, and 1.8R / 2.4R targets.

## Current signal rule
On the latest **closed** 1h candle:
1. The close-to-close move over the preceding six candles must be at most -1.5%.
2. The latest candle must be bullish and close above the previous candle's high.
3. Current volume must be at least 1.0x the median volume of the preceding 20 closed candles.
4. Stop is below the recent local low by a small ATR buffer.

These are initial research defaults, not proven profitable thresholds. Do not interpret a signal as a guarantee of a bottom or a 3% move.

## Run locally
Set BH_SYMBOLS (comma-separated symbols), BH_INTERVAL (default 1h), and optionally TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. Then run:
python -m bottom_hunter_v1.run

Without Telegram credentials, signals are printed to stdout. No exchange credentials are required.

## Validation before use
This prototype is not approved for live decision-making yet. Next step is a no-lookahead historical test with realistic fees/slippage, then out-of-sample testing. Do not merge strategy changes into the existing bot based only on unit tests.
