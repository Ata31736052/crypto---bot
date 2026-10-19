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
def _clean_state(payload):
    """Keep valid episode keys until a successful scan ends that episode.

    Expiring by sent_epoch caused a still-active same-side setup to send again
    every three days. A successful scan clears the key when no setup remains;
    API/data failures deliberately do not clear it.
    """
    if not isinstance(payload, dict):
        return {}
    clean = {}
    for key, value in payload.items():
        if not isinstance(value, dict) or "|" in str(key):
            continue
        try:
            sent_epoch = int(value.get("sent_epoch", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if sent_epoch > 0 and value.get("side") in ("BUY_WATCH", "SELL_WATCH"):
            clean[str(key).upper()] = value
    return clean


def load_state(now=None):
    # 'now' is retained for compatibility with callers/tests; episode validity
    # is based on whether a successful scan still detects the same setup.
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return _clean_state(payload)


def save_state(state):
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)



def is_new_episode(state, symbol, side):
    previous = state.get(str(symbol).upper())
    return not (isinstance(previous, dict) and previous.get("side") == side)


def dedupe_episode_self_test():
    # A still-active setup must remain deduplicated even if its first warning
    # was sent more than three days ago.
    state = _clean_state({"ETHUSDT": {"side": "BUY_WATCH", "sent_epoch": 100, "candle_time": "t1"}})
    assert "ETHUSDT" in state
    assert is_new_episode(state, "ETHUSDT", "BUY_WATCH") is False
    assert is_new_episode(state, "ETHUSDT", "SELL_WATCH") is True
    state.pop("ETHUSDT", None)
    assert is_new_episode(state, "ETHUSDT", "BUY_WATCH") is True
    print("SETUP_FORMING_EPISODE_DEDUPE_SELF_TEST: PASS")
    return True


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
                # A successful evaluation with no active setup ends the previous
                # warning episode. API/data failures above do not clear the state.
                state.pop(str(symbol).upper(), None)
                continue
            detected += 1
            key = str(watch["symbol"]).upper()
            previous = state.get(key)
            if not is_new_episode(state, key, watch["side"]):
                # One alert per continuous same-side setup episode, not one per hour.
                previous["last_candle_time"] = watch["candle_time"]
                continue
            if main.send_telegram_message(main.format_setup_forming_warning(watch)):
                state[key] = {
                    "sent_epoch": now_epoch,
                    "side": watch["side"],
                    "candle_time": watch["candle_time"],
                    "last_candle_time": watch["candle_time"],
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
    if checked == 0:
        raise RuntimeError("Setup Forming scan could not validate any symbol data; refusing a false-success run")
    if failures:
        # Keep a visible, nonzero workflow result when one or more market/send
        # operations failed, so delivery gaps cannot be mistaken for success.
        raise RuntimeError(f"Setup Forming scan completed with {failures} errors")


if __name__ == "__main__":
    if os.getenv("RUN_SETUP_FORMING_ONLY") != "1":
        raise SystemExit("Set RUN_SETUP_FORMING_ONLY=1 to run the warning-only scanner")
    run_scan()
