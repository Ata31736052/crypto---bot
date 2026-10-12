#!/usr/bin/env python3
"""Research-only forward outcome audit for signals on CLOSED 1-hour candles.

signals.csv: symbol,setup,timestamp
candles.csv: symbol,timestamp,open,high,low,close

The signal timestamp must exactly match a closed hourly candle. Entry is that
candle's close; outcome windows begin with the NEXT candle. Gaps invalidate a
horizon rather than silently compressing elapsed time. No signals are generated
and no orders or Telegram messages are sent by this module.
"""
import argparse
import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

REQUIRED_SIGNAL = {"symbol", "setup", "timestamp"}
REQUIRED_CANDLE = {"symbol", "timestamp", "open", "high", "low", "close"}
DEFAULT_HORIZONS_HOURS = (1, 4, 8, 12, 24, 48)


def parse_time(value):
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
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


def load_data(signals_path, candles_path):
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
        candle = {"symbol": symbol, "timestamp": ts}
        for field in ("open", "high", "low", "close"):
            try:
                candle[field] = float(row[field])
            except (TypeError, ValueError):
                raise ValueError(f"invalid {field}: {symbol} {ts.isoformat()}")
            if candle[field] <= 0:
                raise ValueError(f"non-positive {field}: {symbol} {ts.isoformat()}")
        if candle["high"] < max(candle["open"], candle["close"], candle["low"]):
            raise ValueError(f"invalid high: {symbol} {ts.isoformat()}")
        if candle["low"] > min(candle["open"], candle["close"], candle["high"]):
            raise ValueError(f"invalid low: {symbol} {ts.isoformat()}")
        by_symbol[symbol].append(candle)
    for series in by_symbol.values():
        series.sort(key=lambda c: c["timestamp"])
    return signals, by_symbol


def evaluate(signals_path, candles_path, horizons=DEFAULT_HORIZONS_HOURS,
             fee_bps_per_side=10.0, slippage_bps_per_side=5.0):
    """Return one outcome row per signal and complete elapsed-hour horizon.

    Fee and slippage are explicit configurable assumptions, not a claim about
    the user's exchange tier or actual fills. A round trip is charged on entry
    and exit, so net return subtracts twice the per-side assumptions.
    """
    if isinstance(horizons, int):
        horizons = (horizons,)
    horizons = tuple(sorted(set(int(h) for h in horizons)))
    if not horizons or any(h < 1 for h in horizons):
        raise ValueError("horizons must contain positive whole hours")
    if fee_bps_per_side < 0 or slippage_bps_per_side < 0:
        raise ValueError("fee and slippage assumptions must be non-negative")

    signals, by_symbol = load_data(signals_path, candles_path)
    cost_pct = 2.0 * (fee_bps_per_side + slippage_bps_per_side) / 100.0
    results = []
    for row in signals:
        symbol = row["symbol"].strip().upper()
        setup = row["setup"].strip().upper()
        if not setup:
            raise ValueError(f"empty setup for {symbol}")
        ts = parse_time(row["timestamp"])
        series = by_symbol.get(symbol, [])
        index_by_ts = {c["timestamp"]: i for i, c in enumerate(series)}
        if ts not in index_by_ts:
            raise ValueError(f"signal must match a closed candle: {symbol} {ts.isoformat()}")
        i = index_by_ts[ts]
        entry = series[i]["close"]
        future = series[i + 1:]
        # Timestamps must be continuous hourly candles after the signal.
        contiguous = []
        expected = ts + timedelta(hours=1)
        for candle in future:
            if candle["timestamp"] != expected:
                break
            contiguous.append(candle)
            expected += timedelta(hours=1)

        for horizon in horizons:
            window = contiguous[:horizon]
            if len(window) < horizon:
                continue
            # Recovery is horizon-scoped: a recovery after the horizon must not
            # leak into the shorter-horizon report.
            first_below = next((j for j, c in enumerate(window) if c["close"] < entry), None)
            recovery_hours = None
            if first_below is not None:
                recovery_index = next(
                    (j for j in range(first_below + 1, len(window))
                     if window[j]["close"] >= entry),
                    None,
                )
                if recovery_index is not None:
                    recovery_hours = recovery_index + 1
            exit_close = window[-1]["close"]
            gross_return = (exit_close / entry - 1.0) * 100.0
            results.append({
                "symbol": symbol,
                "setup": setup,
                "timestamp": ts.isoformat(),
                "horizon_hours": horizon,
                "entry": entry,
                "exit_close": exit_close,
                "gross_return_pct": gross_return,
                "assumed_round_trip_cost_pct": cost_pct,
                "net_return_pct": gross_return - cost_pct,
                "mfe_pct": (max(c["high"] for c in window) / entry - 1.0) * 100.0,
                "mae_pct": (min(c["low"] for c in window) / entry - 1.0) * 100.0,
                "recovery_to_entry_hours": recovery_hours,
            })
    return results


def summarize(results):
    grouped = defaultdict(list)
    for row in results:
        grouped[(row["setup"], row["horizon_hours"])].append(row)
    summaries = []
    for (setup, horizon), rows in sorted(grouped.items()):
        gross = [r["gross_return_pct"] for r in rows]
        net = [r["net_return_pct"] for r in rows]
        mfes = [r["mfe_pct"] for r in rows]
        maes = [r["mae_pct"] for r in rows]
        recoveries = [r["recovery_to_entry_hours"] for r in rows
                      if r["recovery_to_entry_hours"] is not None]
        summaries.append({
            "setup": setup,
            "horizon_hours": horizon,
            "n": len(rows),
            "win_rate_net_pct": 100.0 * sum(x > 0 for x in net) / len(net),
            "avg_gross_return_pct": statistics.mean(gross),
            "median_gross_return_pct": statistics.median(gross),
            "avg_net_return_pct": statistics.mean(net),
            "median_net_return_pct": statistics.median(net),
            "avg_mfe_pct": statistics.mean(mfes),
            "avg_mae_pct": statistics.mean(maes),
            "recovered_n": len(recoveries),
            "avg_recovery_hours": statistics.mean(recoveries) if recoveries else "",
        })
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signals", required=True, help="CSV: symbol,setup,timestamp")
    parser.add_argument("--candles", required=True, help="CSV of closed 1h candles")
    parser.add_argument("--horizons", default="1,4,8,12,24,48",
                        help="elapsed-hour horizons, default: 1,4,8,12,24,48")
    parser.add_argument("--fee-bps-per-side", type=float, default=10.0,
                        help="assumed fee in basis points per side; default 10")
    parser.add_argument("--slippage-bps-per-side", type=float, default=5.0,
                        help="assumed slippage in basis points per side; default 5")
    parser.add_argument("--out", default="", help="optional detailed outcome CSV path")
    parser.add_argument("--summary-out", default="", help="optional summary CSV path")
    args = parser.parse_args()
    try:
        horizons = tuple(int(x.strip()) for x in args.horizons.split(",") if x.strip())
        results = evaluate(args.signals, args.candles, horizons,
                           args.fee_bps_per_side, args.slippage_bps_per_side)
        summary = summarize(results)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("Research-only CLOSED-candle audit; no live scan or Telegram delivery")
    print(f"Horizons={','.join(map(str, sorted(set(horizons))))}h; "
          f"assumed fee/side={args.fee_bps_per_side:g}bps; "
          f"assumed slippage/side={args.slippage_bps_per_side:g}bps")
    print(f"Complete signal-horizon outcomes: {len(results)}")
    if not summary:
        print("No complete outcomes. Check signal timestamps and contiguous hourly candle coverage.")
    for row in summary:
        print(
            f'{row["setup"]} {row["horizon_hours"]}h: n={row["n"]}, '
            f'net win rate={row["win_rate_net_pct"]:.1f}%, '
            f'avg/median net={row["avg_net_return_pct"]:.3f}%/'
            f'{row["median_net_return_pct"]:.3f}%, '
            f'avg MFE/MAE={row["avg_mfe_pct"]:.3f}%/{row["avg_mae_pct"]:.3f}%, '
            f'recovered={row["recovered_n"]}, '
            f'avg recovery hours={row["avg_recovery_hours"]}'
        )
    if args.out:
        fields = list(results[0]) if results else [
            "symbol", "setup", "timestamp", "horizon_hours", "entry", "exit_close",
            "gross_return_pct", "assumed_round_trip_cost_pct", "net_return_pct",
            "mfe_pct", "mae_pct", "recovery_to_entry_hours",
        ]
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(results)
    if args.summary_out:
        fields = [
            "setup", "horizon_hours", "n", "win_rate_net_pct",
            "avg_gross_return_pct", "median_gross_return_pct",
            "avg_net_return_pct", "median_net_return_pct",
            "avg_mfe_pct", "avg_mae_pct", "recovered_n", "avg_recovery_hours",
        ]
        with open(args.summary_out, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
