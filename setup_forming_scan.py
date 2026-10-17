"""Lightweight 1H Setup Forming scanner.

This process intentionally fetches only 1H candles. It does not evaluate or emit
actionable BUY/SELL entries. Cross-run deduplication state is persisted by the
dedicated GitHub Actions cache workflow.
"""
import json
import os
import time
from pathlib import Path

import main


STATE_PATH = Path("setup_forming_state.json")
MAX_STATE_AGE_SECONDS = 3 * 24 * 60 * 60


def load_state(now=None):
    now = int(now if now is not None else time.time())
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
    except (OSError, ValueError, TypeError):
        return {}
    cutoff = now - MAX_STATE_AGE_SECONDS
    return {
        str(key): value for key, value in payload.items()
        if isinstance(value, dict) and int(value.get("sent_epoch", 0) or 0) >= cutoff
    }


def save_state(state):
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def run_scan():
    now_epoch = int(time.time())
    now_ms = now_epoch * 1000
    state = load_state(now_epoch)
    coins = main.get_scan_coins()
    if not coins:
        raise RuntimeError("Setup Forming scanner found no eligible Binance Spot USDT symbols")

    checked = 0
    detected = 0
    sent = 0
    failures = 0
    print(f"SETUP_FORMING_ONLY start symbols={len(coins)} timeframe=1h")

    for index, symbol in enumerate(coins, start=1):
        try:
            raw = main.get_main_1h_data(symbol)
            if raw is None or raw.empty:
                print(f"SETUP_FORMING_SKIP {symbol}: no 1H candles")
                continue
            frame = main.add_indicators(raw)
            if frame is None or frame.empty:
                print(f"SETUP_FORMING_SKIP {symbol}: indicators unavailable")
                continue
            checked += 1
            watch = main.detect_setup_forming_1h(symbol, frame, now_ms=now_ms)
            if not isinstance(watch, dict):
                continue
            detected += 1
            key = "|".join((watch["symbol"], watch["side"], watch["candle_time"]))
            if key in state:
                continue
            if main.send_telegram_message(main.format_setup_forming_warning(watch)):
                state[key] = {
                    "sent_epoch": now_epoch,
                    "side": watch["side"],
                    "candle_time": watch["candle_time"],
                }
                save_state(state)
                sent += 1
                print(f"SETUP_FORMING_SENT {watch['symbol']} {watch['side']} candle={watch['candle_time']}")
            else:
                failures += 1
                print(f"SETUP_FORMING_SEND_FAILED {watch['symbol']} {watch['side']}")
        except Exception as exc:
            failures += 1
            print(f"SETUP_FORMING_ERROR {symbol}: {type(exc).__name__}: {exc}")

        if index % 10 == 0:
            print(f"SETUP_FORMING_PROGRESS {index}/{len(coins)} checked={checked} detected={detected} sent={sent}")

    save_state(state)
    print(f"SETUP_FORMING_ONLY_DONE checked={checked} detected={detected} sent={sent} failures={failures}")
    if failures:
        # Keep a visible, nonzero workflow result when one or more market/send
        # operations failed, so delivery gaps cannot be mistaken for success.
        raise RuntimeError(f"Setup Forming scan completed with {failures} errors")


if __name__ == "__main__":
    if os.getenv("RUN_SETUP_FORMING_ONLY") != "1":
        raise SystemExit("Set RUN_SETUP_FORMING_ONLY=1 to run the warning-only scanner")
    run_scan()
