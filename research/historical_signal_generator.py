#!/usr/bin/env python3
"""Research-only, point-in-time replay of the current signal engine.

The existing engine is reused unchanged. For each historical 1H close, all
symbol frames are cut to candles fully closed by that decision time, then the
engine is called with that as-of snapshot. No Telegram calls or orders are made.

Important limitation: --symbols is a fixed research cohort, not a historically
reconstructed Binance universe. Results must not be interpreted as live-trading
performance or as proof of profitability.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure importing the production module cannot start its loop or send messages.
os.environ.setdefault("DRY_RUN", "1")
os.environ.setdefault("RUN_ONCE", "0")
os.environ.setdefault("TELEGRAM_TEST_ON_START", "0")

import main as engine  # noqa: E402

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
INTERVAL_MS = {"30m": 30 * 60_000, "1h": 60 * 60_000,
               "4h": 4 * 60 * 60_000, "1d": 24 * 60 * 60_000}
TIMEFRAMES = ("1h", "30m", "4h", "1d")
DEFAULT_SYMBOLS = "BTC,ETH,BNB,SOL,XRP,ADA,DOGE,LTC,LINK,AVAX"


def closed_asof_slice(frame: pd.DataFrame | None, decision_time) -> pd.DataFrame | None:
    """Return only rows whose close_time is strictly before the decision boundary."""
    if frame is None or frame.empty or "close_time" not in frame.columns:
        return None
    decision = pd.Timestamp(decision_time)
    if decision.tzinfo is None:
        decision = decision.tz_localize("UTC")
    else:
        decision = decision.tz_convert("UTC")
    close_times = frame["close_time"]
    if not pd.api.types.is_datetime64_any_dtype(close_times.dtype):
        close_times = pd.to_datetime(close_times, utc=True)
    elif getattr(close_times.dt, "tz", None) is None:
        close_times = close_times.dt.tz_localize("UTC")
    out = frame.loc[close_times < decision].copy()
    return out if not out.empty else None


def fetch_history(symbol: str, interval: str, start_ms: int, end_ms: int,
                  session: requests.Session, pause: float = 0.08) -> pd.DataFrame:
    """Download a bounded Binance Spot kline window with pagination and retries."""
    if interval not in INTERVAL_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    pair = engine.to_binance_usdt_symbol(symbol)
    cursor = int(start_ms)
    rows = []
    step = INTERVAL_MS[interval]
    while cursor < end_ms:
        payload = None
        last_error = None
        for attempt in range(5):
            try:
                response = session.get(
                    BASE_URL,
                    params={"symbol": pair, "interval": interval, "startTime": cursor,
                            "endTime": int(end_ms), "limit": 1000},
                    timeout=25,
                )
                if response.status_code in (418, 429):
                    time.sleep(min(30, 2 ** (attempt + 2)))
                    continue
                response.raise_for_status()
                payload = response.json()
                break
            except Exception as exc:
                last_error = exc
                time.sleep(min(8, 0.5 * (2 ** attempt)))
        if payload is None:
            raise RuntimeError(f"Binance fetch failed for {pair} {interval}: {last_error}")
        if not isinstance(payload, list) or not payload:
            break
        rows.extend(row for row in payload if isinstance(row, list) and len(row) >= 7)
        last_open = int(payload[-1][0])
        next_cursor = last_open + step
        if next_cursor <= cursor:
            raise RuntimeError(f"Pagination stalled for {pair} {interval} at {cursor}")
        cursor = next_cursor
        if len(payload) < 1000:
            break
        time.sleep(pause)

    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([{
        "open_time": int(r[0]), "open": float(r[1]), "high": float(r[2]),
        "low": float(r[3]), "close": float(r[4]), "volume": float(r[5]),
        "close_time": int(r[6]),
    } for r in rows])
    frame = frame.drop_duplicates(subset=["open_time"]).sort_values("open_time")
    frame = frame[(frame["open_time"] >= start_ms) & (frame["close_time"] < end_ms)]
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close", "volume"])
    return frame.reset_index(drop=True)


def add_causal_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    """Use the production indicator function; all input candles are historical."""
    result = engine.add_indicators(frame)
    if result is None or result.empty:
        raise RuntimeError("Production indicator calculation returned no data")
    return result


def btc_regime_asof(cache: dict, decision_time) -> dict:
    """Read the precomputed, prefix-validated BTC indicators as of this time."""
    result = {}
    limits = {"1h": engine.KLINE_LIMIT_MAIN, "1d": engine.KLINE_LIMIT_DAILY}
    for tf, key in (("1h", "1h"), ("1d", "daily")):
        frame = closed_asof_slice(cache.get(tf), decision_time)
        if frame is None:
            result[key] = {"regime": "UNKNOWN", "score": 0,
                           "bullish": False, "bearish": False}
            continue
        frame = frame.tail(limits[tf]).copy()
        if not engine.validate_market_dataframe(frame):
            result[key] = {"regime": "UNKNOWN", "score": 0,
                           "bullish": False, "bearish": False}
            continue
        result[key] = engine._btc_regime_from_row(frame.iloc[-1])
    h1, daily = result["1h"], result["daily"]
    if h1["bullish"] and daily["bullish"]:
        combined = "BULLISH"
    elif h1["bearish"] and daily["bearish"]:
        combined = "BEARISH"
    elif h1["bearish"] and daily["bullish"]:
        combined = "MIXED_BEARISH_1H"
    elif h1["bullish"] and daily["bearish"]:
        combined = "MIXED_BULLISH_1H"
    else:
        combined = "NEUTRAL"
    return {"combined": combined, "combined_score": h1["score"] + daily["score"],
            "1h": h1, "daily": daily}


def signal_rows_for_result(result: dict, symbol: str, decision_time, regime: dict,
                           raw_frames: dict) -> list[dict]:
    candidates = []
    if isinstance(result.get("signal"), dict):
        candidates.append(result["signal"])
    candidates.extend(x for x in (result.get("higher_signals") or []) if isinstance(x, dict))
    rows = []
    for sig in candidates:
        side = str(sig.get("signal", "")).upper()
        if side not in ("BUY", "SELL"):
            continue
        timeframe = str(sig.get("signal_timeframe") or sig.get("timeframe") or "1h").lower()
        timeframe = {"daily": "1d", "1day": "1d", "1h": "1h", "4h": "4h", "30m": "30m"}.get(timeframe, timeframe)
        candle_frame = closed_asof_slice(raw_frames.get(timeframe), decision_time)
        signal_candle_close = (
            candle_frame["close_time"].iloc[-1].isoformat()
            if candle_frame is not None else pd.Timestamp(decision_time).isoformat()
        )
        # Point-in-time context for diagnosing late entries and nearby resistance.
        # These features use only candles closed by decision_time.
        h1 = closed_asof_slice(raw_frames.get("1h"), decision_time)
        close_now = _num(h1["close"].iloc[-1], 0.0) if h1 is not None and not h1.empty else 0.0
        def prior_return(bars):
            if h1 is None or len(h1) <= bars or close_now <= 0:
                return None
            old_close = _num(h1["close"].iloc[-1 - bars], 0.0)
            return round((close_now / old_close - 1.0) * 100.0, 4) if old_close > 0 else None
        def distance_from_high(bars):
            if h1 is None or h1.empty or close_now <= 0:
                return None
            window = h1.tail(bars)
            if window.empty:
                return None
            high = _num(window["high"].max(), 0.0)
            return round((high / close_now - 1.0) * 100.0, 4) if high > 0 else None
        rows.append({
            "decision_time": pd.Timestamp(decision_time).isoformat(),
            "signal_candle_close_time": signal_candle_close,
            "symbol": symbol,
            "side": side,
            "engine": str(sig.get("engine") or sig.get("signal_mode") or "UNKNOWN"),
            "timeframe": timeframe,
            "score": sig.get("score"),
            "quality_score": sig.get("professional_quality_score"),
            "regime": regime.get("combined", "UNKNOWN"),
            "signal_entry": sig.get("entry"),
            "stop_loss": sig.get("stop_loss"),
            "tp1": sig.get("tp1"),
            "tp2": sig.get("tp2"),
            "prior_24h_return_pct": prior_return(24),
            "prior_72h_return_pct": prior_return(72),
            "distance_7d_high_pct": distance_from_high(24 * 7),
            "distance_30d_high_pct": distance_from_high(24 * 30),
            "reasons": " | ".join(str(x) for x in (sig.get("reasons") or [])[:12]),
        })
    return rows


def evaluate_barriers(signal: dict, future: pd.DataFrame, horizon: int,
                      cost_pct: float = 0.4) -> dict:
    """Conservative next-open replay; if SL and TP1 touch in one candle, SL wins."""
    side = str(signal.get("side", "")).upper()
    entry = _num(signal.get("actual_entry"))
    stop = _num(signal.get("stop_loss"))
    target = _num(signal.get("tp1"))
    if side not in ("BUY", "SELL") or entry <= 0 or stop <= 0 or target <= 0:
        return {"event": "INVALID_LEVELS", "net_return_pct": None, "bars": 0}
    # The signal is not a tradable entry if the next 1H open has already
    # crossed its stop or TP1. Do not fabricate a zero-return trade in this case.
    if side == "BUY" and entry <= stop:
        return {"event": "ENTRY_INVALIDATED_BY_STOP", "net_return_pct": None, "bars": 0}
    if side == "BUY" and entry >= target:
        return {"event": "ENTRY_INVALIDATED_BY_TP1", "net_return_pct": None, "bars": 0}
    if side == "SELL" and entry >= stop:
        return {"event": "ENTRY_INVALIDATED_BY_STOP", "net_return_pct": None, "bars": 0}
    if side == "SELL" and entry <= target:
        return {"event": "ENTRY_INVALIDATED_BY_TP1", "net_return_pct": None, "bars": 0}
    window = future.head(horizon)
    if len(window) < horizon:
        return {"event": "INCOMPLETE_WINDOW", "net_return_pct": None, "bars": len(window)}
    for idx, row in enumerate(window.itertuples(index=False), start=1):
        op, hi, lo, close = map(float, (row.open, row.high, row.low, row.close))
        if side == "BUY":
            if op <= stop:
                exit_price, event = op, "GAP_STOP"
            elif op >= target:
                exit_price, event = op, "GAP_TP1"
            elif lo <= stop and hi >= target:
                exit_price, event = stop, "SL_FIRST_SAME_CANDLE"
            elif lo <= stop:
                exit_price, event = stop, "SL"
            elif hi >= target:
                exit_price, event = target, "TP1"
            else:
                continue
            gross = (exit_price / entry - 1.0) * 100.0
        else:
            if op >= stop:
                exit_price, event = op, "GAP_STOP"
            elif op <= target:
                exit_price, event = op, "GAP_TP1"
            elif hi >= stop and lo <= target:
                exit_price, event = stop, "SL_FIRST_SAME_CANDLE"
            elif hi >= stop:
                exit_price, event = stop, "SL"
            elif lo <= target:
                exit_price, event = target, "TP1"
            else:
                continue
            gross = (entry / exit_price - 1.0) * 100.0 if exit_price > 0 else None
        return {"event": event, "bars": idx, "exit_price": exit_price,
                "gross_return_pct": gross,
                "net_return_pct": gross - cost_pct if gross is not None else None}
    last = window.iloc[-1]
    close = float(last["close"])
    gross = ((close / entry - 1.0) if side == "BUY" else (entry / close - 1.0)) * 100.0
    return {"event": "HORIZON_CLOSE", "bars": horizon, "exit_price": close,
            "gross_return_pct": gross, "net_return_pct": gross - cost_pct}


def _num(value, default=0.0):
    try:
        out = float(value)
        return out if pd.notna(out) else default
    except (TypeError, ValueError):
        return default


def generate(args) -> dict:
    if args.end:
        end_time = pd.Timestamp(args.end)
        end_time = end_time.tz_localize("UTC") if end_time.tzinfo is None else end_time.tz_convert("UTC")
    else:
        end_time = pd.Timestamp.now(tz="UTC")
    eval_start = end_time - pd.Timedelta(days=args.evaluation_days)
    data_start = eval_start - pd.Timedelta(days=args.warmup_days)
    start_ms, end_ms = int(data_start.timestamp() * 1000), int(end_time.timestamp() * 1000)
    symbols = list(dict.fromkeys(s.strip().upper().removesuffix("USDT")
                                 for s in args.symbols.split(",") if s.strip()))
    if not symbols:
        raise ValueError("Provide at least one symbol")
    if "BTC" not in symbols:
        symbols.insert(0, "BTC")

    session = requests.Session()
    raw = {}
    raw_candles = {}
    coverage = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "decision_engine": "current main.py analyze_one_symbol",
                "evaluation_start": eval_start.isoformat(), "evaluation_end": end_time.isoformat(),
                "warmup_days": args.warmup_days, "evaluation_days": args.evaluation_days,
                "symbols_requested": symbols, "universe_note":
                "Fixed symbol cohort; not a point-in-time historical Binance universe.",
                "lookahead_controls": [
                    "Only candles with close_time strictly before decision_time are visible.",
                    "Indicators are computed from historical candles and checked for prefix invariance.",
                    "Signal outcomes start at the next 1H candle open, never at the signal candle close.",
                    "Same-candle SL/TP1 ambiguity resolves conservatively as SL first."
                ], "candles": {}}

    all_symbols = list(dict.fromkeys(symbols + ["BTC"]))
    for sym in all_symbols:
        raw[sym] = {}
        raw_candles[sym] = {}
        for tf in TIMEFRAMES:
            frame = fetch_history(sym, tf, start_ms, end_ms, session, args.request_pause)
            if frame.empty:
                raw[sym][tf] = None
                raw_candles[sym][tf] = None
                coverage["candles"][f"{sym}_{tf}"] = {"rows": 0, "status": "MISSING"}
                continue
            raw_candles[sym][tf] = frame
            print(f"Downloaded {sym} {tf}: {len(frame)} closed candles")
            enriched = add_causal_indicators(frame)
            raw[sym][tf] = enriched
            coverage["candles"][f"{sym}_{tf}"] = {
                "rows": len(enriched), "first_open": enriched["open_time"].iloc[0].isoformat(),
                "last_close": enriched["close_time"].iloc[-1].isoformat(), "status": "OK"
            }

    # Verify a prefix and full-history indicator calculation agree for a sample
    # point. This catches accidental future-dependent indicator columns.
    prefix_checks = []
    for sym in all_symbols:
        for tf in TIMEFRAMES:
            frame = raw.get(sym, {}).get(tf)
            if frame is None or len(frame) < 220:
                continue
            cut = max(200, min(len(frame) - 2, len(frame) // 2))
            source = frame[["open_time", "close_time", "open", "high", "low", "close", "volume"]].copy()
            prefix = add_causal_indicators(source.iloc[:cut].copy())
            full = add_causal_indicators(source.copy()).iloc[:cut].reset_index(drop=True)
            prefix = prefix.reset_index(drop=True)
            cols = [c for c in prefix.columns if c in full.columns and
                    (pd.api.types.is_numeric_dtype(prefix[c]) or pd.api.types.is_bool_dtype(prefix[c]))]
            mismatch = []
            for col in cols:
                a = prefix[col]
                b = full[col]
                if pd.api.types.is_bool_dtype(a) or pd.api.types.is_bool_dtype(b):
                    ok = a.fillna(False).equals(b.fillna(False))
                else:
                    av = pd.to_numeric(a, errors="coerce").to_numpy(dtype=float)
                    bv = pd.to_numeric(b, errors="coerce").to_numpy(dtype=float)
                    sa, sb = pd.Series(av), pd.Series(bv)
                    same_nan = sa.isna().equals(sb.isna())
                    valid = sa.notna() & sb.notna()
                    finite = sa.loc[valid].sub(sb.loc[valid]).abs().lt(1e-8).all()
                    ok = bool(same_nan and finite)
                if not ok:
                    mismatch.append(col)
            prefix_checks.append({"symbol": sym, "timeframe": tf, "cut_index": cut,
                                  "mismatch_columns": mismatch})
            if mismatch:
                raise RuntimeError(f"Indicator prefix invariance failed for {sym} {tf}: {mismatch[:8]}")
    coverage["indicator_prefix_checks"] = prefix_checks
    if not prefix_checks:
        raise RuntimeError("No symbol had enough candles for an indicator prefix check")

    # The production analyzer calls prepare_symbol_data(symbol); replace only
    # that data boundary so it receives a closed, as-of snapshot. Engine rules
    # and gates remain the existing production functions.
    current_decision = {"time": None, "symbol": None}
    def historical_prepare(symbol):
        t = current_decision["time"]
        # Use the already computed indicator frames. The prefix-invariance
        # audit above verifies that indicator values do not change when future
        # candles are appended, so slicing these frames as-of is causal and
        # avoids recalculating every timeframe for every historical decision.
        cached = raw.get(symbol)
        if not cached or t is None:
            return None
        limits = {
            "1h": engine.KLINE_LIMIT_MAIN,
            "30m": engine.KLINE_LIMIT_CONFIRM,
            "4h": engine.KLINE_LIMIT_4H,
            "1d": engine.KLINE_LIMIT_DAILY,
        }
        frames = {}
        for tf in TIMEFRAMES:
            frame = closed_asof_slice(cached.get(tf), t)
            if frame is None:
                frames[tf] = None
                continue
            frame = frame.tail(limits[tf]).copy()
            if not engine.validate_market_dataframe(frame):
                frames[tf] = None
                continue
            # Indicators were computed once for this symbol/timeframe before
            # replay and verified by prefix-invariance checks.
            frames[tf] = frame
        if frames["1h"] is None or frames["30m"] is None:
            return None
        if len(frames["1h"]) < 200 or len(frames["30m"]) < 80:
            return None
        return frames

    original_prepare = engine.prepare_symbol_data
    original_debug = engine.DEBUG_MODE
    engine.prepare_symbol_data = historical_prepare
    engine.DEBUG_MODE = False
    signals = []
    errors = Counter()
    decision_count = 0
    try:
        btc_1h = raw["BTC"].get("1h")
        if btc_1h is None:
            raise RuntimeError("BTC 1H history unavailable")
        decisions = btc_1h.loc[
            (btc_1h["open_time"] >= eval_start) & (btc_1h["open_time"] < end_time),
            "close_time"
        ].tolist()
        # Convert candle close timestamps to the next boundary at which the
        # just-closed candle is available to the signal engine.
        for close_time in decisions:
            decision_time = pd.Timestamp(close_time) + pd.Timedelta(milliseconds=1)
            current_decision["time"] = decision_time
            regime = btc_regime_asof(raw["BTC"], decision_time)
            for symbol in symbols:
                cached = raw.get(symbol)
                if not cached or cached.get("1h") is None or cached.get("30m") is None:
                    errors["missing_symbol_data"] += 1
                    continue
                current_decision["symbol"] = symbol
                asof_1h = closed_asof_slice(cached.get("1h"), decision_time)
                if asof_1h is None or len(asof_1h) < 200:
                    errors["insufficient_1h_history"] += 1
                    continue
                next_rows = cached["1h"].loc[cached["1h"]["open_time"] >= decision_time]
                if next_rows.empty:
                    errors["no_next_open"] += 1
                    continue
                actual_entry = float(next_rows.iloc[0]["open"])
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = engine.analyze_one_symbol(symbol, regime)
                except Exception:
                    errors["engine_exception"] += 1
                    continue
                decision_count += 1
                for row in signal_rows_for_result(result, symbol, decision_time, regime, cached):
                    row["actual_entry"] = actual_entry
                    row["planned_entry_gap_pct"] = (
                        (actual_entry / _num(row.get("signal_entry"), actual_entry) - 1.0) * 100.0
                        if _num(row.get("signal_entry"), 0) > 0 else None
                    )
                    # Attach barrier outcomes from the actual next 1H open.
                    entry_frame = raw_candles[symbol]["1h"]
                    entry_index = entry_frame.index[entry_frame["open_time"] >= decision_time]
                    if len(entry_index):
                        start_pos = int(entry_index[0])
                        future = entry_frame.iloc[start_pos:]
                    else:
                        future = entry_frame.iloc[0:0]
                    for horizon in (8, 24, 48):
                        out = evaluate_barriers(row, future, horizon, args.cost_pct)
                        for k, v in out.items():
                            row[f"{horizon}h_{k}"] = v
                    signals.append(row)
            if decision_count and decision_count % max(1, args.progress_every) == 0:
                print(f"Replay progress: {decision_count} symbol decisions; {len(signals)} signals")
    finally:
        engine.prepare_symbol_data = original_prepare
        engine.DEBUG_MODE = original_debug

    # Keep alert count and independent decision-candle count distinct.
    dedup = {}
    for row in signals:
        key = (row["symbol"], row["signal_candle_close_time"], row["side"], row["engine"], row["timeframe"])
        dedup.setdefault(key, row)
    unique_signals = list(dedup.values())
    coverage["run"] = {
        "decision_evaluations": decision_count, "raw_signal_rows": len(signals),
        "deduplicated_signal_rows": len(unique_signals),
        "duplicate_signal_rows_removed": len(signals) - len(unique_signals),
        "engine_errors": dict(errors), "cost_assumption_round_trip_pct": args.cost_pct,
        "outcome_horizons_hours": [8, 24, 48],
        "note": "Cost is a sensitivity assumption, not a claim about actual fees or fills."
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    signal_path = out_dir / "historical_signals.csv"
    summary_path = out_dir / "historical_summary.csv"
    coverage_path = out_dir / "historical_coverage.json"
    fields = sorted({key for row in unique_signals for key in row})
    with signal_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique_signals)

    summary = []
    buckets = defaultdict(list)
    for row in unique_signals:
        buckets[(row["engine"], row["side"], row["regime"])].append(row)
    for (engine_name, side, regime_name), group in sorted(buckets.items()):
        gaps = [_num(x.get("planned_entry_gap_pct"), float("nan")) for x in group]
        gaps = [abs(v) for v in gaps if pd.notna(v)]
        item = {
            "engine": engine_name, "side": side, "regime": regime_name, "signals": len(group),
            "entry_invalidated_by_stop": sum(str(x.get("8h_event", "")).startswith("ENTRY_INVALIDATED_BY_STOP") for x in group),
            "entry_invalidated_by_tp1": sum(str(x.get("8h_event", "")).startswith("ENTRY_INVALIDATED_BY_TP1") for x in group),
            "entry_gap_abs_gt_1pct": sum(v > 1.0 for v in gaps),
            "median_abs_planned_entry_gap_pct": round(float(pd.Series(gaps).median()), 4) if gaps else None,
        }
        for horizon in (8, 24, 48):
            vals = [_num(x.get(f"{horizon}h_net_return_pct"), float("nan")) for x in group]
            vals = [v for v in vals if pd.notna(v)]
            item[f"{horizon}h_evaluated"] = len(vals)
            item[f"{horizon}h_mean_net_pct"] = round(sum(vals) / len(vals), 4) if vals else None
            item[f"{horizon}h_positive_pct"] = round(100 * sum(v > 0 for v in vals) / len(vals), 2) if vals else None
            item[f"{horizon}h_SL_first"] = sum(str(x.get(f"{horizon}h_event", "")).startswith(("SL", "GAP_STOP")) for x in group)
            item[f"{horizon}h_TP1_first"] = sum(str(x.get(f"{horizon}h_event", "")).startswith(("TP1", "GAP_TP1")) for x in group)
        summary.append(item)
    summary_fields = sorted({key for row in summary for key in row})
    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary)
    coverage_path.write_text(json.dumps(coverage, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"coverage": str(coverage_path), "signals": str(signal_path),
                      "summary": str(summary_path), "run": coverage["run"]}, indent=2))
    return coverage


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=DEFAULT_SYMBOLS,
                        help="Comma-separated fixed cohort of Binance Spot base symbols")
    parser.add_argument("--evaluation-days", type=int, default=180)
    parser.add_argument("--warmup-days", type=int, default=260)
    parser.add_argument("--end", help="UTC ISO timestamp; defaults to current UTC time")
    parser.add_argument("--cost-pct", type=float, default=0.4,
                        help="Round-trip cost sensitivity in percentage points")
    parser.add_argument("--request-pause", type=float, default=0.08)
    parser.add_argument("--progress-every", type=int, default=500)
    parser.add_argument("--out-dir", default="artifacts/historical-replay")
    args = parser.parse_args(argv)
    if args.evaluation_days < 1 or args.warmup_days < 210:
        parser.error("evaluation-days must be >=1 and warmup-days >=210 for EMA200 context")
    if args.cost_pct < 0:
        parser.error("cost-pct must be non-negative")
    return args


if __name__ == "__main__":
    generate(parse_args())
