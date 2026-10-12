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
import statistics
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    from research.entry_exit_location_audit import assess_trade_location
except ModuleNotFoundError:  # supports direct execution as a script from research/
    from entry_exit_location_audit import assess_trade_location

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


def prior_move_metrics(prior, entry, side, atr):
    """Describe how far price had already moved using only closed pre-signal candles."""
    metrics = {}
    side = str(side or "BUY").upper()
    last_close = prior[-1]["close"] if prior else None
    for hours in (12, 24, 48):
        key = f"prior_return_{hours}h_pct"
        if len(prior) > hours and prior[-hours - 1]["close"] > 0:
            metrics[key] = (last_close / prior[-hours - 1]["close"] - 1) * 100
        else:
            metrics[key] = ""
    for hours in (24, 48, 72):
        window = prior[-hours:]
        if len(window) < hours:
            metrics[f"range_position_{hours}h_pct"] = ""
            metrics[f"directional_progress_{hours}h_pct"] = ""
            metrics[f"distance_to_directional_obstacle_{hours}h_atr"] = ""
            continue
        low = min(c["low"] for c in window)
        high = max(c["high"] for c in window)
        width = high - low
        if width <= 0:
            metrics[f"range_position_{hours}h_pct"] = ""
            metrics[f"directional_progress_{hours}h_pct"] = ""
            metrics[f"distance_to_directional_obstacle_{hours}h_atr"] = ""
            continue
        position = (entry - low) / width * 100
        directional = position if side != "SELL" else 100 - position
        obstacle = high - entry if side != "SELL" else entry - low
        metrics[f"range_position_{hours}h_pct"] = position
        metrics[f"directional_progress_{hours}h_pct"] = directional
        metrics[f"distance_to_directional_obstacle_{hours}h_atr"] = obstacle / atr if atr and atr > 0 else ""
    progress = metrics.get("directional_progress_72h_pct", "")
    if progress == "":
        metrics["progress_bucket_72h"] = "UNAVAILABLE"
    elif progress < 33.333333:
        metrics["progress_bucket_72h"] = "EARLY_THIRD"
    elif progress < 66.666667:
        metrics["progress_bucket_72h"] = "MIDDLE_THIRD"
    else:
        metrics["progress_bucket_72h"] = "LATE_THIRD"
    return metrics


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

    move_metrics = prior_move_metrics(prior, entry, str(signal.get("signal", "BUY")).upper(), atr)
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
        **move_metrics,
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


def policy_accepts(row, policy):
    if row.get("status") != "ASSESSED":
        return None
    if policy == "STRICT_1P5_ATR_BOTH_TARGETS":
        return bool(row.get("location_gate_accepted"))
    reasons = set(filter(None, str(row.get("rejection_reasons", "")).split(";")))
    # The stored reasons were generated with the strict 1.5 ATR threshold;
    # candidate policies apply their own numeric room threshold below.
    reasons.discard("BUY_TOO_CLOSE_TO_HISTORICAL_RESISTANCE")
    reasons.discard("SELL_TOO_CLOSE_TO_HISTORICAL_SUPPORT")
    if "STRUCTURAL_STOP_TOO_WIDE" in reasons:
        return False
    if "TP1_BLOCKED_BY_RESISTANCE" in reasons or "TP1_BLOCKED_BY_SUPPORT" in reasons:
        return False
    room = row.get("room_to_obstacle_atr", "")
    room = float(room) if room not in ("", None) else None
    threshold = 1.0 if policy == "TP1_ONLY_1P0_ATR" else 0.5
    if room is not None and room < threshold:
        return False
    # TP2 may be obstructed under these research-only candidates; it must be
    # capped before the obstacle in any future implementation.
    return True


def build_summary(results):
    summary = []
    policies = ("STRICT_1P5_ATR_BOTH_TARGETS", "TP1_ONLY_1P0_ATR", "TP1_ONLY_0P5_ATR")
    for split in ("ALL", "EARLY_SAMPLE", "HOLDOUT"):
        split_rows = [
            r for r in results if r.get("status") == "ASSESSED"
            and (split == "ALL" or r.get("chronological_split") == split)
        ]
        for setup in ("TREND_HEURISTIC", "BOTTOM_HUNTER_HEURISTIC"):
            setup_rows = [r for r in split_rows if r.get("setup") == setup]
            for policy in policies:
                for gate in ("REJECTED", "ACCEPTED"):
                    group = [r for r in setup_rows if policy_accepts(r, policy) is (gate == "ACCEPTED")]
                    if not group:
                        continue
                    for horizon in (8, 24, 48):
                        values, mfes, maes = [], [], []
                        for row in group:
                            ret, mfe, mae = (row.get(f"{key}_{horizon}h_pct", "") for key in ("close_return", "mfe", "mae"))
                            if ret not in ("", None) and mfe not in ("", None) and mae not in ("", None):
                                values.append(float(ret))
                                mfes.append(float(mfe))
                                maes.append(float(mae))
                        if not values:
                            continue
                        summary.append({
                            "row_type": "OUTCOME", "split": split, "setup": setup,
                            "policy": policy, "gate_result": gate, "horizon_hours": horizon,
                            "n": len(values), "avg_close_return_pct": sum(values) / len(values),
                            "median_close_return_pct": statistics.median(values),
                            "positive_close_return_pct": 100 * sum(v > 0 for v in values) / len(values),
                            "avg_mfe_pct": sum(mfes) / len(mfes), "avg_mae_pct": sum(maes) / len(maes),
                            "reason": "", "count": "",
                        })
    # Descriptive, pre-declared move-stage comparison; no threshold is selected from these results.
    for split in ("ALL", "EARLY_SAMPLE", "HOLDOUT"):
        split_rows = [
            r for r in results if r.get("status") == "ASSESSED"
            and (split == "ALL" or r.get("chronological_split") == split)
        ]
        for setup in ("TREND_HEURISTIC", "BOTTOM_HUNTER_HEURISTIC"):
            setup_rows = [r for r in split_rows if r.get("setup") == setup]
            for bucket in ("EARLY_THIRD", "MIDDLE_THIRD", "LATE_THIRD", "UNAVAILABLE"):
                group = [r for r in setup_rows if r.get("progress_bucket_72h") == bucket]
                if not group:
                    continue
                for horizon in (8, 24, 48):
                    values = [float(r[f"close_return_{horizon}h_pct"]) for r in group
                              if r.get(f"close_return_{horizon}h_pct") not in ("", None)]
                    mfes = [float(r[f"mfe_{horizon}h_pct"]) for r in group
                            if r.get(f"mfe_{horizon}h_pct") not in ("", None)]
                    maes = [float(r[f"mae_{horizon}h_pct"]) for r in group
                            if r.get(f"mae_{horizon}h_pct") not in ("", None)]
                    if not values:
                        continue
                    prior24 = [float(r["prior_return_24h_pct"]) for r in group
                               if r.get("prior_return_24h_pct") not in ("", None)]
                    summary.append({
                        "row_type": "MOVE_STAGE_OUTCOME", "split": split, "setup": setup,
                        "policy": "DESCRIPTIVE_ONLY_NO_GATE", "gate_result": bucket,
                        "horizon_hours": horizon, "n": len(values),
                        "avg_close_return_pct": sum(values) / len(values),
                        "median_close_return_pct": statistics.median(values),
                        "positive_close_return_pct": 100 * sum(v > 0 for v in values) / len(values),
                        "avg_mfe_pct": sum(mfes) / len(mfes) if mfes else "",
                        "avg_mae_pct": sum(maes) / len(maes) if maes else "",
                        "avg_prior_return_24h_pct": sum(prior24) / len(prior24) if prior24 else "",
                        "avg_directional_progress_72h_pct": statistics.mean(
                            float(r["directional_progress_72h_pct"]) for r in group
                            if r.get("directional_progress_72h_pct") not in ("", None)
                        ) if any(r.get("directional_progress_72h_pct") not in ("", None) for r in group) else "",
                        "reason": "", "count": "",
                    })
    reason_counts = defaultdict(int)
    for row in results:
        if row.get("status") != "ASSESSED":
            continue
        for reason in filter(None, str(row.get("rejection_reasons", "")).split(";")):
            reason_counts[(row.get("setup", "UNKNOWN"), reason)] += 1
    for (setup, reason), count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
        summary.append({
            "row_type": "STRICT_GATE_REASON", "split": "ALL", "setup": setup,
            "policy": "STRICT_1P5_ATR_BOTH_TARGETS", "gate_result": "REJECTED",
            "horizon_hours": "", "n": "", "avg_close_return_pct": "",
            "median_close_return_pct": "", "positive_close_return_pct": "",
            "avg_mfe_pct": "", "avg_mae_pct": "", "reason": reason, "count": count,
        })
    return summary


def replay(history_path, out_path, min_room_atr=1.5, summary_out_path=""):
    with open(history_path, encoding="utf-8") as handle:
        history = json.load(handle)
    if not isinstance(history, list):
        raise ValueError("signals history must be a JSON list")
    raw_valid = [r for r in history if r.get("symbol") and r.get("timestamp")]
    if not raw_valid:
        raise ValueError("no usable signal records found")
    # Repeated scans can log the same symbol/side/candle more than once. Keep
    # the earliest recorded instance per candle to avoid overweighting duplicates.
    valid = []
    seen_events = set()
    for row in sorted(raw_valid, key=lambda r: parse_time(r["timestamp"])):
        candle_key = str(row.get("candle_time") or parse_time(row["timestamp"]).replace(minute=0, second=0, microsecond=0).isoformat())
        key = (str(row["symbol"]).strip().upper(), str(row.get("signal", "BUY")).upper(), candle_key)
        if key in seen_events:
            continue
        seen_events.add(key)
        valid.append(row)
    deduplicated_count = len(raw_valid) - len(valid)

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

    unique_times = sorted({parse_time(r["timestamp"]) for r in valid})
    cutoff_index = min(len(unique_times) - 1, max(0, int(len(unique_times) * 0.70)))
    holdout_cutoff = unique_times[cutoff_index]
    for row in results:
        if row.get("timestamp"):
            ts = parse_time(row["timestamp"])
            row["chronological_split"] = "HOLDOUT" if ts >= holdout_cutoff else "EARLY_SAMPLE"

    fields = sorted({key for row in results for key in row})
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    counts = defaultdict(int)
    for row in results:
        counts[row.get("status", "UNKNOWN")] += 1
    print("Research-only historical location replay; no signals, trades, or Telegram.")
    print(f"History records: {len(raw_valid)}; deduplicated same-candle events: {deduplicated_count}; evaluated events: {len(valid)}")
    print(f"Symbols requested: {len(by_symbol)}; candle sets fetched: {len(cache)}")
    print(f"Rows written: {len(results)} -> {out_path}")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    assessed = [r for r in results if r.get("status") == "ASSESSED"]
    print(f"Chronological holdout begins at: {holdout_cutoff.isoformat()}")
    if assessed:
        for setup in ("TREND_HEURISTIC", "BOTTOM_HUNTER_HEURISTIC"):
            rows = [r for r in assessed if r.get("setup") == setup and r.get("chronological_split") == "HOLDOUT"]
            if not rows:
                continue
            print(f"{setup} HOLDOUT n={len(rows)}")
            for policy in ("STRICT_1P5_ATR_BOTH_TARGETS", "TP1_ONLY_1P0_ATR", "TP1_ONLY_0P5_ATR"):
                accepted = [r for r in rows if policy_accepts(r, policy) is True]
                print(f"  {policy}: accepted={len(accepted)}/{len(rows)} ({100*len(accepted)/len(rows):.1f}%)")
                for horizon in (8, 24, 48):
                    returns = [float(r[f"close_return_{horizon}h_pct"]) for r in accepted
                               if r.get(f"close_return_{horizon}h_pct") not in ("", None)]
                    maes = [float(r[f"mae_{horizon}h_pct"]) for r in accepted
                            if r.get(f"mae_{horizon}h_pct") not in ("", None)]
                    if returns and maes:
                        print(f"    accepted {horizon}h: coverage={len(returns)}, "
                              f"avg return={sum(returns)/len(returns):.3f}%, "
                              f"median={statistics.median(returns):.3f}%, "
                              f"positive={100*sum(v > 0 for v in returns)/len(returns):.1f}%, "
                              f"avg MAE={sum(maes)/len(maes):.3f}%")
    summary = build_summary(results)
    if summary_out_path:
        fields = ["row_type", "split", "setup", "policy", "gate_result", "horizon_hours", "n",
                  "positive_close_return_pct", "avg_mfe_pct", "avg_mae_pct",
                  "avg_prior_return_24h_pct", "avg_directional_progress_72h_pct", "reason", "count"]
        with open(summary_out_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(summary)
        print(f"Summary written: {summary_out_path}")
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
    parser.add_argument("--summary-out", default="historical_entry_location_summary.csv")
    parser.add_argument("--min-room-atr", type=float, default=1.5)
    args = parser.parse_args()
    return replay(args.history, args.out, args.min_room_atr, args.summary_out)


if __name__ == "__main__":
    raise SystemExit(main())
