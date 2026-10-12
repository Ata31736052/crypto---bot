#!/usr/bin/env python3
"""Research-only replay of recorded signals against historical Binance Spot candles.

Fetches public hourly klines for symbols already present in signals_history.json,
evaluates only candles closed before each recorded signal, and reports nearby
historical support/resistance plus subsequent close returns/MFE/MAE. Never emits
signals, calls Telegram, or places orders.
"""
import argparse
import csv
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from research.entry_exit_location_audit import assess_trade_location

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
HORIZONS = (1, 4, 8, 12, 24, 48)
BOTTOM_CUES = (
    "near 72h low", "close to recent low", "recent low",
    "rsi recovering", "fibonacci 0.618", "early reversal",
)


def parse_time(value):
    value = str(value).strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return dt.astimezone(timezone.utc)


def classify_setup(signal):
    text = " ".join(str(x) for x in signal.get("reasons", [])).lower()
    if any(cue in text for cue in BOTTOM_CUES):
        return "BOTTOM_HUNTER_HEURISTIC"
    return "TREND_HEURISTIC"


def true_range(candle, previous_close):
    return max(
        candle["high"] - candle["low"],
        abs(candle["high"] - previous_close),
        abs(candle["low"] - previous_close),
    )


def atr_from_closed_candles(candles, period=14):
    if len(candles) < period + 1:
        return None
    ranges = [
        true_range(candles[i], candles[i - 1]["close"])
        for i in range(len(candles) - period, len(candles))
    ]
    value = sum(ranges) / len(ranges)
    return value if math.isfinite(value) and value > 0 else None


def normalize_klines(rows):
    candles = []
    for row in rows:
        candles.append({
            "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "close_time": datetime.fromtimestamp(row[6] / 1000, tz=timezone.utc),
        })
    return candles


def fetch_symbol_candles(session, symbol, start, end):
    params = {
        "symbol": symbol + "USDT",
        "interval": "1h",
        "startTime": int(start.timestamp() * 1000),
        "endTime": int(end.timestamp() * 1000),
        "limit": 1000,
    }
    response = session.get(BASE_URL, params=params, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"unexpected Binance response for {symbol}: {payload}")
    return normalize_klines(payload)


def _signal_candle(entry):
    # Synthetic row is excluded by assess_trade_location; its sole purpose is to
    # mark the evaluation boundary without injecting signal/future OHLC into levels.
    return {"open": entry, "high": entry, "low": entry, "close": entry}


def analyze_signal(signal, candles, min_room_atr=1.5):
    symbol = str(signal.get("symbol", "")).strip().upper()
    timestamp = parse_time(signal["timestamp"])
    try:
        entry = float(signal.get("entry", signal.get("price")))
    except (TypeError, ValueError):
        entry = float("nan")
    if not math.isfinite(entry) or entry <= 0:
        return {"symbol": symbol, "timestamp": timestamp.isoformat(), "status": "INVALID_ENTRY"}

    # A candle is eligible only after its close time is at or before signal time.
    prior = [c for c in candles if c["close_time"] <= timestamp]
    prior.sort(key=lambda c: c["close_time"])
    if len(prior) < 20:
        return {
            "symbol": symbol, "timestamp": timestamp.isoformat(),
            "setup": classify_setup(signal), "entry": entry,
            "status": "INSUFFICIENT_CLOSED_HISTORY", "closed_candles_before_signal": len(prior),
        }
    atr = atr_from_closed_candles(prior)
    if atr is None:
        return {
            "symbol": symbol, "timestamp": timestamp.isoformat(),
            "setup": classify_setup(signal), "entry": entry,
            "status": "ATR_UNAVAILABLE", "closed_candles_before_signal": len(prior),
        }

    assessment = assess_trade_location(
        [*prior, _signal_candle(entry)],
        entry=entry,
        atr=atr,
        side=str(signal.get("signal", "BUY")).upper(),
        min_room_atr=min_room_atr,
    )
    future = sorted((c for c in candles if c["open_time"] >= timestamp), key=lambda c: c["close_time"])
    result = {
        "symbol": symbol,
        "timestamp": timestamp.isoformat(),
        "setup": classify_setup(signal),
        "signal_side": str(signal.get("signal", "BUY")).upper(),
        "entry": entry,
        "atr": atr,
        "status": "ASSESSED",
        "closed_candles_before_signal": len(prior),
        "historical_resistance": assessment["historical_resistance"] or "",
        "historical_support": assessment["historical_support"] or "",
        "room_to_obstacle_atr": assessment["room_to_obstacle_atr"] if assessment["room_to_obstacle_atr"] is not None else "",
        "location_gate_accepted": assessment["accepted"],
        "rejection_reasons": ";".join(assessment["rejection_reasons"]),
        "structural_stop": assessment["stop_loss"],
        "structural_tp1": assessment["tp1"],
        "structural_tp2": assessment["tp2"],
        "structural_stop_pct": assessment["stop_distance_pct"],
    }
    for horizon in HORIZONS:
        target = timestamp + timedelta(hours=horizon)
        eligible = [c for c in future if c["close_time"] >= target]
        if not eligible:
            result[f"close_return_{horizon}h_pct"] = ""
            result[f"mfe_{horizon}h_pct"] = ""
            result[f"mae_{horizon}h_pct"] = ""
            continue
        endpoint = eligible[0]["close_time"]
        window = [c for c in future if c["close_time"] <= endpoint]
        result[f"close_return_{horizon}h_pct"] = (eligible[0]["close"] / entry - 1) * 100
        result[f"mfe_{horizon}h_pct"] = (max(c["high"] for c in window) / entry - 1) * 100
        result[f"mae_{horizon}h_pct"] = (min(c["low"] for c in window) / entry - 1) * 100
    return result


def replay(history_path, out_path, min_room_atr=1.5):
    with open(history_path, encoding="utf-8") as handle:
        history = json.load(handle)
    if not isinstance(history, list):
        raise ValueError("signals history must be a JSON list")
    valid = [r for r in history if r.get("symbol") and r.get("timestamp")]
    if not valid:
        raise ValueError("no usable signal records found")

    by_symbol = defaultdict(list)
    for row in valid:
        by_symbol[str(row["symbol"]).strip().upper()].append(row)
    start = min(parse_time(r["timestamp"]) for r in valid) - timedelta(hours=130)
    end = max(parse_time(r["timestamp"]) for r in valid) + timedelta(hours=50)
    session = requests.Session()
    cache = {}
    errors = []
    for symbol in sorted(by_symbol):
        try:
            cache[symbol] = fetch_symbol_candles(session, symbol, start, end)
        except Exception as exc:
            errors.append({"symbol": symbol, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(0.08)

    results = []
    for signal in valid:
        symbol = str(signal["symbol"]).strip().upper()
        if symbol not in cache:
            results.append({
                "symbol": symbol,
                "timestamp": parse_time(signal["timestamp"]).isoformat(),
                "setup": classify_setup(signal),
                "status": "BINANCE_DATA_UNAVAILABLE",
            })
            continue
        try:
            results.append(analyze_signal(signal, cache[symbol], min_room_atr))
        except (ValueError, KeyError, TypeError) as exc:
            results.append({
                "symbol": symbol,
                "timestamp": parse_time(signal["timestamp"]).isoformat(),
                "setup": classify_setup(signal),
                "status": f"ASSESSMENT_ERROR:{type(exc).__name__}",
            })

    fields = sorted({key for row in results for key in row})
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    counts = defaultdict(int)
    for row in results:
        counts[row.get("status", "UNKNOWN")] += 1
    print("Research-only historical location replay; no signals, trades, or Telegram.")
    print(f"History records: {len(valid)}; symbols requested: {len(by_symbol)}; candle sets fetched: {len(cache)}")
    print(f"Rows written: {len(results)} -> {out_path}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    assessed = [r for r in results if r.get("status") == "ASSESSED"]
    if assessed:
        for setup in ("TREND_HEURISTIC", "BOTTOM_HUNTER_HEURISTIC"):
            rows = [r for r in assessed if r.get("setup") == setup]
            if not rows:
                continue
            rejected = sum(r.get("location_gate_accepted") is False for r in rows)
            returns = [float(r["close_return_8h_pct"]) for r in rows if r.get("close_return_8h_pct") not in ("", None)]
            maes = [float(r["mae_8h_pct"]) for r in rows if r.get("mae_8h_pct") not in ("", None)]
            print(
                f"{setup}: n={len(rows)}, location-rejected={rejected} "
                f"({100*rejected/len(rows):.1f}%), "
                f"8h coverage={len(returns)}, "
                f"avg 8h close return={sum(returns)/len(returns):.3f}% "
                f"avg 8h MAE={sum(maes)/len(maes):.3f}%"
                if returns and maes else
                f"{setup}: n={len(rows)}, location-rejected={rejected}; insufficient 8h coverage"
            )
    if errors:
        print(f"Binance fetch failures: {len(errors)}")
        for item in errors:
            print(f"FETCH_ERROR {item['symbol']}: {item['error']}")
    # Partial coverage is explicitly reported, but API hiccups do not mask the
    # generated report artifact. CI tests validate the evaluator separately.
    return 0 if results else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="signals_history.json")
    parser.add_argument("--out", default="historical_entry_location_replay.csv")
    parser.add_argument("--min-room-atr", type=float, default=1.5)
    args = parser.parse_args()
    return replay(args.history, args.out, args.min_room_atr)


if __name__ == "__main__":
    raise SystemExit(main())
