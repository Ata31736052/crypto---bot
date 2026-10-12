#!/usr/bin/env python3
"""Research-only closed-candle signal timing audit.

Input signals.csv: symbol,setup,timestamp
Input candles.csv: symbol,timestamp,open,high,low,close

Timestamps must be UTC ISO-8601. Signal timestamp must match a CLOSED candle.
Only candles strictly AFTER the signal candle are used for outcomes, preventing
same-candle look-ahead. This tool does not generate signals or place trades.
"""
import argparse
import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_SIGNAL = {"symbol", "setup", "timestamp"}
REQUIRED_CANDLE = {"symbol", "timestamp", "open", "high", "low", "close"}


def parse_time(value):
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return dt.astimezone(timezone.utc)


def read_csv(path, required):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = required - fields
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(sorted(missing))}")
        return list(reader)


def evaluate(signals_path, candles_path, horizon=8):
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    signals = read_csv(signals_path, REQUIRED_SIGNAL)
    candle_rows = read_csv(candles_path, REQUIRED_CANDLE)

    by_symbol = defaultdict(list)
    seen = set()
    for row in candle_rows:
        symbol = row["symbol"].strip().upper()
        ts = parse_time(row["timestamp"])
        key = (symbol, ts)
        if key in seen:
            raise ValueError(f"duplicate candle: {symbol} {ts.isoformat()}")
        seen.add(key)
        candle = {"timestamp": ts}
        for field in ("open", "high", "low", "close"):
            candle[field] = float(row[field])
            if candle[field] <= 0:
                raise ValueError(f"non-positive {field}: {symbol} {ts.isoformat()}")
        if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
            raise ValueError(f"invalid high: {symbol} {ts.isoformat()}")
        if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
            raise ValueError(f"invalid low: {symbol} {ts.isoformat()}")
        by_symbol[symbol].append(candle)

    for symbol in by_symbol:
        by_symbol[symbol].sort(key=lambda c: c["timestamp"])

    results = []
    for row in signals:
        symbol = row["symbol"].strip().upper()
        setup = row["setup"].strip().upper()
        ts = parse_time(row["timestamp"])
        series = by_symbol.get(symbol, [])
        index_by_ts = {c["timestamp"]: i for i, c in enumerate(series)}
        if ts not in index_by_ts:
            raise ValueError(f"signal must match a closed candle: {symbol} {ts.isoformat()}")
        i = index_by_ts[ts]
        entry = series[i]["close"]
        future = series[i + 1:i + 1 + horizon]
        if len(future) < horizon:
            continue  # incomplete horizon is not silently treated as an outcome
        last_close = future[-1]["close"]
        results.append({
            "symbol": symbol,
            "setup": setup,
            "timestamp": ts,
            "entry": entry,
            "return_pct": (last_close / entry - 1.0) * 100.0,
            "mfe_pct": (max(c["high"] for c in future) / entry - 1.0) * 100.0,
            "mae_pct": (min(c["low"] for c in future) / entry - 1.0) * 100.0,
        })
    return results


def summarize(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[result["setup"]].append(result)
    lines = []
    for setup in sorted(grouped):
        rows = grouped[setup]
        returns = [r["return_pct"] for r in rows]
        mfes = [r["mfe_pct"] for r in rows]
        maes = [r["mae_pct"] for r in rows]
        lines.append({
            "setup": setup,
            "n": len(rows),
            "avg_return_pct": statistics.mean(returns),
            "median_return_pct": statistics.median(returns),
            "avg_mfe_pct": statistics.mean(mfes),
            "avg_mae_pct": statistics.mean(maes),
        })
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True, help="CSV: symbol,setup,timestamp")
    parser.add_argument("--candles", required=True, help="CSV: symbol,timestamp,open,high,low,close")
    parser.add_argument("--horizon", type=int, default=8, help="number of fully closed candles AFTER signal candle (default: 8)")
    parser.add_argument("--out", default="", help="optional summary CSV output path")
    args = parser.parse_args()
    try:
        results = evaluate(args.signals, args.candles, args.horizon)
        summary = summarize(results)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Research-only audit | horizon={args.horizon} subsequent closed candles")
    print(f"Complete outcomes: {len(results)}")
    if not summary:
        print("No complete outcomes. Check timestamp alignment and candle coverage.")
    for row in summary:
        print("{setup}: n={n}, avg={avg_return_pct:.3f}%, median={median_return_pct:.3f}%, "
              "avg_MFE={avg_mfe_pct:.3f}%, avg_MAE={avg_mae_pct:.3f}%".format(**row))
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "setup", "n", "avg_return_pct", "median_return_pct", "avg_mfe_pct", "avg_mae_pct"
            ])
            writer.writeheader()
            writer.writerows(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
