#!/usr/bin/env python3
"""Closed-candle historical replay of the repository signal engine. No orders or Telegram."""
import json, os, time, cProfile, pstats, io, resource, math
from pathlib import Path
import pandas as pd
import requests
import main
from portfolio_ledger import portfolio_ledger, portfolio_ledger_self_test

BASE = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision")
SYMBOLS = [s.strip().upper().replace("/", "").replace("-", "") for s in (os.getenv("BACKTEST_SYMBOLS") or "ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT").split(",") if s.strip()]
DAYS = max(30, min(365, int((os.getenv("BACKTEST_DAYS") or "180"))))
FEE_BPS = float((os.getenv("BACKTEST_FEE_BPS") or "10"))
SLIPPAGE_BPS = float((os.getenv("BACKTEST_SLIPPAGE_BPS") or "5"))
OUT = Path("backtest-results"); OUT.mkdir(exist_ok=True)
MS = {"1h":3600000,"30m":1800000,"4h":14400000,"1d":86400000}
# Daily/4H EMA200 context requires substantially more than 30 days of warm-up.
WARMUP_DAYS = 250
WARMUP_BARS = 200
TIMEFRAME_LIMITS = {"1h": main.KLINE_LIMIT_MAIN, "30m": main.KLINE_LIMIT_CONFIRM,
                    "4h": main.KLINE_LIMIT_4H, "1d": main.KLINE_LIMIT_DAILY}
SESSION = requests.Session()

def filter_closed_before_end(d, end_ms, include_boundary_open=False):
    """Keep only closed candles before end; optionally retain the exact boundary-open 1H execution bar."""
    if d is None or d.empty:
        return d
    boundary=pd.to_datetime(end_ms,unit="ms",utc=True)
    if include_boundary_open:
        # The candle opening exactly at the exclusive end is execution-only:
        # it supplies the next-bar open for a signal on the final in-window candle.
        # The replay loop must never evaluate it as a signal candle.
        return d[(d["close_time"] < boundary) | (d["open_time"] == boundary)]
    return d[d["close_time"] < boundary]

def validate_finite_ohlcv(frame, context="OHLCV"):
    """Fail closed if any OHLCV row contains missing, malformed, or non-finite numeric data."""
    if frame is None or frame.empty:
        return True
    columns = ("open", "high", "low", "close", "volume")
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise RuntimeError(f"{context} is missing columns: {', '.join(missing)}")
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any():
            raise RuntimeError(f"{context} contains missing or invalid {column} values")
        if not all(math.isfinite(float(value)) for value in values):
            raise RuntimeError(f"{context} contains non-finite {column} values")
    return True


def validate_boundary_execution_candle(frame, end_time):
    """Require the exact next-hour candle used only to execute the final in-window signal."""
    boundary = pd.Timestamp(end_time)
    if boundary.tzinfo is None:
        raise ValueError("end_time must be timezone-aware")
    boundary = boundary.tz_convert("UTC")
    if frame is None or frame.empty:
        raise RuntimeError("Missing boundary-open execution candle")
    if "open_time" not in frame or "close_time" not in frame:
        raise RuntimeError("Boundary execution candle is missing timestamp columns")
    matches = frame[frame["open_time"] == boundary]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one boundary-open execution candle")
    candle = matches.iloc[0]
    if pd.isna(candle["close_time"]) or candle["close_time"] <= boundary:
        raise RuntimeError("Boundary execution candle has an invalid close_time")
    for column in ("open", "high", "low", "close", "volume"):
        try:
            value = float(candle[column])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise RuntimeError(f"Boundary execution candle has invalid {column}")
        if not math.isfinite(value):
            raise RuntimeError(f"Boundary execution candle has non-finite {column}")
    if any(float(candle[column]) <= 0 for column in ("open", "high", "low", "close")) or float(candle["volume"]) < 0:
        raise RuntimeError("Boundary execution candle has non-positive price or negative volume")
    return True


def replay_signal_indices(frame, start_index, end_time):
    """Validate replay boundary and return signal indices; boundary row is execution-only."""
    validate_boundary_execution_candle(frame, end_time)
    boundary = pd.Timestamp(end_time).tz_convert("UTC")
    boundary_index = int(frame["open_time"].searchsorted(boundary))
    if boundary_index >= len(frame) or frame.iloc[boundary_index]["open_time"] != boundary:
        raise RuntimeError("Boundary execution candle is missing or misplaced")
    if boundary_index < 1 or frame.iloc[boundary_index - 1]["close_time"] >= boundary:
        raise RuntimeError("No valid closed signal candle immediately before execution boundary")
    return range(max(0, int(start_index)), boundary_index)


def fetch(symbol, tf, start_ms, end_ms, include_boundary_open=False, now=None, signal_boundary_ms=None):
    rows=[]; cursor=start_ms
    while cursor < end_ms:
        r=SESSION.get(f"{BASE}/api/v3/klines",params={"symbol":symbol,"interval":tf,"startTime":cursor,"endTime":end_ms,"limit":1000},timeout=30)
        r.raise_for_status(); batch=r.json()
        if not isinstance(batch,list): raise RuntimeError(f"Bad Binance response: {symbol} {tf}")
        if not batch: break
        rows.extend(batch); nxt=int(batch[-1][0])+MS[tf]
        if nxt<=cursor: raise RuntimeError("Pagination stalled")
        cursor=nxt
        if len(batch)<1000: break
        time.sleep(.08)
    if not rows: return pd.DataFrame()
    d=pd.DataFrame(rows,columns=["open_time","open","high","low","close","volume","close_time","qv","trades","tb","tq","ignore"])
    d["open_time"]=pd.to_datetime(d.open_time,unit="ms",utc=True); d["close_time"]=pd.to_datetime(d.close_time,unit="ms",utc=True)
    for c in ("open","high","low","close","volume"): d[c]=pd.to_numeric(d[c],errors="coerce")
    # Treat end_ms as an exclusive closed-candle boundary. Binance endTime can
    # include a candle whose open_time equals the boundary but whose close is later.
    # The boundary-open bar is execution-only and may still be forming at "now";
    # preserve its open price when explicitly requested, without admitting other open bars.
    clock = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if clock.tzinfo is None:
        clock = clock.tz_localize("UTC")
    else:
        clock = clock.tz_convert("UTC")
    boundary = pd.to_datetime(signal_boundary_ms if signal_boundary_ms is not None else end_ms, unit="ms", utc=True)
    closed_or_execution = d.close_time < clock
    if include_boundary_open:
        closed_or_execution = closed_or_execution | (d.open_time == boundary)
    d=d[closed_or_execution]
    if signal_boundary_ms is None:
        d=filter_closed_before_end(d,end_ms,include_boundary_open=include_boundary_open)
    else:
        # Separate the signal cutoff from the wider data window used for exits.
        data_cutoff = pd.to_datetime(end_ms, unit="ms", utc=True)
        d=d[(d.close_time < data_cutoff) | (d.open_time == boundary)]
    validate_finite_ohlcv(d, f"{symbol} {tf}")
    d=d.dropna(subset=["open","high","low","close","volume"])
    return d.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)[["open_time","close_time","open","high","low","close","volume"]]


def closed_end_cutoff_self_test():
    """A fixed end boundary must exclude candles that close at/after that boundary."""
    end=pd.Timestamp("2026-10-13T12:00:00Z")
    sample=pd.DataFrame({
        "open_time":pd.to_datetime(["2026-10-13T10:00:00Z","2026-10-13T11:00:00Z"],utc=True),
        "close_time":pd.to_datetime(["2026-10-13T10:59:59.999Z","2026-10-13T11:59:59.999Z"],utc=True),
    })
    sample=pd.concat([sample,pd.DataFrame({
        "open_time":pd.to_datetime(["2026-10-13T12:00:00Z"],utc=True),
        "close_time":pd.to_datetime(["2026-10-13T12:59:59.999Z"],utc=True),
    })],ignore_index=True)
    end_ms=int(end.timestamp()*1000)
    kept=filter_closed_before_end(sample,end_ms)
    assert len(kept)==2 and kept.close_time.max() < end, "post-boundary candle leaked into signal window"
    with_execution_bar=filter_closed_before_end(sample,end_ms,include_boundary_open=True)
    assert len(with_execution_bar)==3 and with_execution_bar.iloc[-1].open_time==end, "boundary-open execution candle was not retained"
    assert with_execution_bar.iloc[-1].close_time > end, "test execution candle must close after the signal window"
    print("CLOSED_END_CUTOFF_SELF_TEST: PASS")
    return True

def fetch_clock_boundary_self_test():
    """A fixed end boundary retains its execution-open even while that candle is forming."""
    end = pd.Timestamp("2026-10-13T12:00:00Z")
    end_ms = int(end.timestamp() * 1000)
    rows = []
    for open_time, close_time, price in (
        (end - pd.Timedelta(hours=1), end - pd.Timedelta(milliseconds=1), 100.0),
        (end, end + pd.Timedelta(hours=1) - pd.Timedelta(milliseconds=1), 101.0),
        (end + pd.Timedelta(hours=1), end + pd.Timedelta(hours=2) - pd.Timedelta(milliseconds=1), 102.0),
    ):
        rows.append([
            int(open_time.timestamp() * 1000), str(price), str(price + 1), str(price - 1),
            str(price), "10", int(close_time.timestamp() * 1000), "1000", 10, "5", "500", "0",
        ])

    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return rows

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    original_session = SESSION
    try:
        globals()["SESSION"] = FakeSession()
        # The execution candle is not closed at this clock time, but its open is known.
        now = end + pd.Timedelta(minutes=30)
        with_execution = fetch(
            "ETHUSDT", "1h", end_ms - 2 * MS["1h"], end_ms,
            include_boundary_open=True, now=now,
        )
        assert len(with_execution) == 2, "forming boundary execution candle was dropped or a future candle leaked"
        assert with_execution.iloc[-1]["open_time"] == end
        assert float(with_execution.iloc[-1]["open"]) == 101.0
        without_execution = fetch(
            "ETHUSDT", "1h", end_ms - 2 * MS["1h"], end_ms,
            include_boundary_open=False, now=now,
        )
        assert len(without_execution) == 1 and without_execution.iloc[-1]["open_time"] == end - pd.Timedelta(hours=1)
    finally:
        globals()["SESSION"] = original_session
    print("FETCH_CLOCK_BOUNDARY_SELF_TEST: PASS")
    return True


def boundary_execution_candle_self_test():
    """Cover present, missing, duplicated, and malformed boundary execution bars."""
    end = pd.Timestamp("2026-10-13T12:00:00Z")
    frame = pd.DataFrame({
        "open_time": pd.to_datetime(["2026-10-13T11:00:00Z", "2026-10-13T12:00:00Z"], utc=True),
        "close_time": pd.to_datetime(["2026-10-13T11:59:59.999Z", "2026-10-13T12:59:59.999Z"], utc=True),
        "open": [100.0, 101.0], "high": [102.0, 103.0],
        "low": [99.0, 100.0], "close": [101.0, 102.0], "volume": [10.0, 12.0],
    })
    assert validate_boundary_execution_candle(frame, end) is True
    # The execution candle must be distinct from the final in-window signal candle.
    assert frame.iloc[-1]["open_time"] == end
    assert frame.iloc[-2]["close_time"] < end
    for invalid, message in (
        (frame.iloc[:-1].copy(), "missing boundary bar"),
        (pd.concat([frame, frame.iloc[-1:]], ignore_index=True), "duplicate boundary bar"),
    ):
        try:
            validate_boundary_execution_candle(invalid, end)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"{message} was not rejected")
    malformed = frame.copy()
    malformed.loc[1, "close_time"] = end
    try:
        validate_boundary_execution_candle(malformed, end)
    except RuntimeError:
        pass
    else:
        raise AssertionError("invalid boundary close_time was not rejected")
    malformed = frame.copy()
    malformed.loc[1, "open"] = float("nan")
    try:
        validate_boundary_execution_candle(malformed, end)
    except RuntimeError:
        pass
    else:
        raise AssertionError("invalid boundary price was not rejected")
    # Infinity must be rejected for every OHLCV field, not merely NaN.
    for column in ("open", "high", "low", "close", "volume"):
        for bad in (float("inf"), float("-inf")):
            malformed = frame.copy()
            malformed.loc[1, column] = bad
            try:
                validate_boundary_execution_candle(malformed, end)
            except RuntimeError:
                pass
            else:
                raise AssertionError(f"non-finite {column} value {bad} was not rejected")
    # Integration-style filter -> replay regression: without the opt-in, the
    # boundary row is excluded; with it, that row is retained for execution only.
    end_ms = int(end.timestamp() * 1000)
    signal_only = filter_closed_before_end(frame, end_ms)
    assert len(signal_only) == 1 and signal_only.iloc[-1]["close_time"] < end, (
        "default filter leaked the boundary execution candle into the signal window"
    )
    filtered = filter_closed_before_end(frame, end_ms, include_boundary_open=True)
    assert len(filtered) == 2 and filtered.iloc[-1]["open_time"] == end, (
        "filter did not retain the boundary-open execution candle"
    )
    # Post-boundary candles are outcome-only and must not enter signal generation.
    outcome_rows = pd.DataFrame({
        "open_time": pd.to_datetime(["2026-10-13T13:00:00Z", "2026-10-13T14:00:00Z"], utc=True),
        "close_time": pd.to_datetime(["2026-10-13T13:59:59.999Z", "2026-10-13T14:59:59.999Z"], utc=True),
        "open": [102.0, 104.0], "high": [106.0, 107.0],
        "low": [101.0, 103.0], "close": [105.0, 106.0], "volume": [10.0, 10.0],
    })
    replay_frame = pd.concat([filtered, outcome_rows], ignore_index=True)
    signal_indices = list(replay_signal_indices(replay_frame, 0, end))
    boundary_index = int(replay_frame["open_time"].searchsorted(end))
    assert signal_indices == [0], f"future outcome candles leaked into signal indices: {signal_indices}"
    assert boundary_index not in signal_indices, "boundary execution candle was evaluated as a signal"
    assert boundary_index < len(replay_frame) - 1, "test requires post-boundary outcome candles"
    # Exercise the actual execution function using the replay's next-bar index.
    # This proves the boundary-open candle's OPEN is consumed as the entry price,
    # rather than merely checking that the dataframe contains the expected value.
    signal_index = signal_indices[0]
    trade, _ = simulate(
        "TESTUSDT", "BUY", filtered.iloc[signal_index]["close_time"],
        signal_index + 1, replay_frame, 1.0, 95, "STRONG",
        {"entry": 100.0, "stop_loss": 98.0},
    )
    assert trade is not None, "simulate did not produce a trade from the boundary execution candle"
    assert trade["entry"] == 101.0, (
        f"simulate did not consume boundary candle OPEN; actual entry={trade['entry']}"
    )
    assert trade["exit_reason"] == "TP1", f"post-boundary closed candle did not drive exit: {trade['exit_reason']}"
    assert pd.Timestamp(trade["exit_time"]) == pd.Timestamp("2026-10-13T13:59:59.999Z"), (
        "exit did not use the first completed post-boundary candle"
    )
    assert pd.Timestamp(trade["entry_time"]) == end, (
        "simulate entry timestamp did not match the boundary-open execution candle"
    )
    assert signal_index + 1 == boundary_index, (
        "replay's next-bar execution index did not point at the boundary candle"
    )
    for invalid in (filtered.iloc[:-1].copy(), filtered.assign(open_time=[filtered.iloc[0]["open_time"], end + pd.Timedelta(hours=1)])):
        try:
            replay_signal_indices(invalid, 0, end)
        except RuntimeError:
            pass
        else:
            raise AssertionError("replay accepted missing/misplaced boundary candle")
    print("BOUNDARY_EXECUTION_CANDLE_SELF_TEST: PASS")
    return True


def finite_ohlcv_self_test():
    """Reject NaN and both infinities in every OHLCV field on any row."""
    frame = pd.DataFrame({
        "open": [100.0, 101.0], "high": [102.0, 103.0],
        "low": [99.0, 100.0], "close": [101.0, 102.0],
        "volume": [10.0, 12.0],
    })
    assert validate_finite_ohlcv(frame, "self-test") is True
    for row_index in range(len(frame)):
        for column in ("open", "high", "low", "close", "volume"):
            for bad in (float("nan"), float("inf"), float("-inf")):
                malformed = frame.copy()
                malformed.loc[row_index, column] = bad
                try:
                    validate_finite_ohlcv(malformed, "self-test")
                except RuntimeError:
                    pass
                else:
                    raise AssertionError(
                        f"non-finite {column} at row {row_index} ({bad}) was not rejected"
                    )
    print("FINITE_OHLCV_SELF_TEST: PASS")
    return True


def prepare(d):
    if d.empty: return d
    x=main.add_indicators(d.copy())
    return x.sort_values("open_time").reset_index(drop=True) if x is not None and not x.empty else pd.DataFrame()


def validate_warmup(frames, start_time, symbol="", required_timeframes=None):
    """Fail closed unless each requested timeframe has enough closed pre-test candles."""
    required_timeframes = tuple(required_timeframes or ("1h", "30m", "4h", "1d"))
    failures = []
    for tf in required_timeframes:
        frame = frames.get(tf)
        if frame is None or frame.empty or "close_time" not in frame:
            failures.append(f"{tf}: missing history")
            continue
        before_start = frame[frame["close_time"] <= start_time]
        if len(before_start) < WARMUP_BARS:
            failures.append(f"{tf}: {len(before_start)} closed pre-test bars < {WARMUP_BARS}")
    if failures:
        raise RuntimeError(f"Insufficient indicator warm-up for {symbol or 'market'}: " + "; ".join(failures))
    return True


def validate_warmup_self_test():
    """Regression test: adequate warm-up passes; one missing required bar fails closed."""
    start = pd.Timestamp("2026-10-01T00:00:00Z")
    base = pd.date_range(end=start, periods=WARMUP_BARS, freq="1h", tz="UTC")
    frame = pd.DataFrame({"close_time": base})
    assert validate_warmup({"1h": frame}, start, "TEST", ("1h",)) is True
    try:
        validate_warmup({"1h": frame.iloc[1:]}, start, "TEST", ("1h",))
    except RuntimeError:
        pass
    else:
        raise AssertionError("warm-up guard accepted fewer than required historical candles")
    print("HISTORICAL_WARMUP_SELF_TEST: PASS")
    return True


def signal_diagnostics(df, side):
    """Capture signal-time location/momentum fields to diagnose late entries."""
    if df is None or len(df) < 22:
        return {}
    row=df.iloc[-1]
    close=float(row.get("close",0) or 0); atr=float(row.get("atr",0) or 0)
    if close <= 0 or atr <= 0:
        return {}
    prior=df.iloc[-21:-1]
    highs=pd.to_numeric(prior["high"],errors="coerce")
    lows=pd.to_numeric(prior["low"],errors="coerce")
    resistance=highs[highs>close].min() if (highs>close).any() else float("nan")
    support=lows[lows<close].max() if (lows<close).any() else float("nan")
    room=(float(resistance)-close)/atr if side=="BUY" and pd.notna(resistance) else ((close-float(support))/atr if side=="SELL" and pd.notna(support) else float("nan"))
    out={"signal_close":close,"signal_atr":atr,"atr_pct":float(row.get("atr_percent",0) or 0),
         "rsi":float(row.get("rsi",0) or 0),"adx":float(row.get("adx",0) or 0),
         "volume_ratio":float(row.get("volume_ratio",0) or 0),
         "ema21_extension_atr":((close-float(row.get("ema21",close) or close))/atr)*(1 if side=="BUY" else -1),
         "room_to_obstacle_atr":room}
    for n in (6,12,24):
        past=float(df.iloc[-1-n]["close"]) if len(df)>n else 0
        out[f"directional_move_{n}h_pct"]=((close/past-1)*100*(1 if side=="BUY" else -1)) if past>0 else float("nan")
    hi=float(highs.max()) if highs.notna().any() else close
    lo=float(lows.min()) if lows.notna().any() else close
    out["range_position_20"]=((close-lo)/(hi-lo)) if hi>lo else 0.5
    # Backtest-only guard uses confirmed 2-left/2-right swing pivots, not every
    # candle high/low. All five candles in a pivot are already closed at signal time.
    prior = df.iloc[-21:-1]
    prior_highs = pd.to_numeric(prior["high"], errors="coerce").reset_index(drop=True)
    prior_lows = pd.to_numeric(prior["low"], errors="coerce").reset_index(drop=True)
    swing_highs, swing_lows = [], []
    for i in range(2, len(prior) - 2):
        h = prior_highs.iloc[i]
        l = prior_lows.iloc[i]
        h_left = prior_highs.iloc[i-2:i]
        h_right = prior_highs.iloc[i+1:i+3]
        l_left = prior_lows.iloc[i-2:i]
        l_right = prior_lows.iloc[i+1:i+3]
        if pd.notna(h) and h > h_left.max() and h >= h_right.max():
            swing_highs.append(float(h))
        if pd.notna(l) and l < l_left.min() and l <= l_right.min():
            swing_lows.append(float(l))
    if side == "BUY":
        levels = [level for level in swing_highs if level > close]
        if not levels:
            room_atr = float("nan")
            allowed, reason = True, "ENTRY_LOCATION_NO_CONFIRMED_RESISTANCE"
        else:
            room_atr = (min(levels) - close) / atr
            allowed = room_atr >= 0.80
            reason = f"ENTRY_LOCATION_SWING_ROOM_{room_atr:.2f}_ATR"
    else:
        levels = [level for level in swing_lows if level < close]
        if not levels:
            room_atr = float("nan")
            allowed, reason = True, "ENTRY_LOCATION_NO_CONFIRMED_SUPPORT"
        else:
            room_atr = (close - max(levels)) / atr
            allowed = room_atr >= 0.80
            reason = f"ENTRY_LOCATION_SWING_ROOM_{room_atr:.2f}_ATR"
    # Keep the reported diagnostic metric identical to the actual confirmed-swing
    # guard. The raw 20-candle high/low estimate above is intentionally replaced.
    out["room_to_obstacle_atr"] = room_atr
    out["entry_guard_allowed"] = bool(allowed)
    out["entry_guard_reason"] = reason
    return out


def entry_location_guard_self_test():
    """Reject only when a confirmed directional swing obstacle is too close."""
    def frame_with_levels(side, obstacle):
        rows = []
        for i in range(22):
            close = 100.0
            high, low = 99.0, 101.0
            if 1 <= i <= 20:
                high, low = (99.0, 101.0)
            rows.append({"open":close,"high":high,"low":low,"close":close,
                         "atr":2.0,"atr_percent":2.0,"rsi":55.0,"adx":25.0,
                         "volume_ratio":1.5,"ema21":100.0})
        # Prior-window index 8 is a clear swing; adjacent highs/lows remain non-pivots.
        if side == "BUY":
            rows[1+8]["high"] = obstacle
        else:
            rows[1+8]["low"] = obstacle
        return pd.DataFrame(rows)

    # A close non-pivot high is ignored when a farther confirmed swing is the true obstacle.
    rows = frame_with_levels("BUY", 104.0)
    rows.loc[1+7, "high"] = 100.5
    d = signal_diagnostics(rows, "BUY")
    assert d["entry_guard_allowed"] is True and "2.00_ATR" in d["entry_guard_reason"], d
    assert abs(d["room_to_obstacle_atr"] - 2.0) < 1e-9, d
    # Confirmed swing only 0.5 ATR away is rejected and diagnostic distance agrees.
    d = signal_diagnostics(frame_with_levels("BUY", 101.0), "BUY")
    assert d["entry_guard_allowed"] is False and "0.50_ATR" in d["entry_guard_reason"], d
    assert abs(d["room_to_obstacle_atr"] - 0.5) < 1e-9, d
    # Same directional rule applies to confirmed support for SELL.
    d = signal_diagnostics(frame_with_levels("SELL", 96.0), "SELL")
    assert d["entry_guard_allowed"] is True and "2.00_ATR" in d["entry_guard_reason"], d
    assert abs(d["room_to_obstacle_atr"] - 2.0) < 1e-9, d
    d = signal_diagnostics(frame_with_levels("SELL", 99.0), "SELL")
    assert d["entry_guard_allowed"] is False and "0.50_ATR" in d["entry_guard_reason"], d
    assert abs(d["room_to_obstacle_atr"] - 0.5) < 1e-9, d
    print("ENTRY_LOCATION_SWING_GUARD_SELF_TEST: PASS")
    return True


def simulate(symbol,side,signal_time,entry_i,h1,atr,score,strength,signal_obj=None):
    row=h1.iloc[entry_i]; entry=float(row.open)
    if entry<=0 or atr<=0:return None,entry_i
    # Reuse the production engine's validated stop distance, re-anchored to
    # the next candle's executable open. This preserves structural Bottom Hunter
    # stops and the 4H/Daily stop multiplier instead of forcing every engine
    # to use the generic 1H ATR stop.
    engine_entry=float((signal_obj or {}).get("entry",0) or (signal_obj or {}).get("price",0) or 0)
    engine_stop=float((signal_obj or {}).get("stop_loss",0) or 0)
    risk=abs(engine_entry-engine_stop) if engine_entry>0 and engine_stop>0 else 0.0
    if risk<=0:
        risk=atr*float(getattr(main,"SL_ATR_MULTIPLIER",1.5))
    rr1=float(getattr(main,"TP1_RR",1.8)); rr2=float(getattr(main,"TP2_RR",2.4))
    if side=="BUY": sl,tp1,tp2=entry-risk,entry+risk*rr1,entry+risk*rr2
    else: sl,tp1,tp2=entry+risk,entry-risk*rr1,entry-risk*rr2
    end_i=min(len(h1)-1,entry_i+72); exitp=float(h1.iloc[end_i].close); reason="TIME_EXIT_72H"; xi=end_i
    # Conservative OHLC ambiguity policy: SL wins over targets; if both targets
    # are touched in one candle, credit only TP1 because intrabar order is unknown.
    for j in range(entry_i,end_i+1):
        c=h1.iloc[j]; hi,lo=float(c.high),float(c.low)
        slhit=(lo<=sl if side=="BUY" else hi>=sl)
        t2=(hi>=tp2 if side=="BUY" else lo<=tp2)
        t1=(hi>=tp1 if side=="BUY" else lo<=tp1)
        if slhit: exitp,reason,xi=sl,"SL",j; break
        if t1: exitp,reason,xi=tp1,"TP1",j; break
        if t2: exitp,reason,xi=tp2,"TP2",j; break
    gross=((exitp-entry)/entry*100) if side=="BUY" else ((entry-exitp)/entry*100)
    costs=2*(FEE_BPS+SLIPPAGE_BPS)/100
    path=[]
    for k in range(entry_i, xi+1):
        candle=h1.iloc[k]
        path.append({"time":str(candle.close_time),"price":float(exitp if k==xi else candle.close)})
    return {"symbol":symbol,"side":side,"signal_time":str(signal_time),"entry_time":str(row.open_time),"entry":entry,"stop_loss":sl,"tp1":tp1,"tp2":tp2,"exit_time":str(h1.iloc[xi].close_time),"exit":exitp,"exit_reason":reason,"gross_pct":round(gross,4),"cost_pct":round(costs,4),"net_pct":round(gross-costs,4),"bars_held":xi-entry_i,"score":score,"strength":strength,"_path":path},xi

def closed_prefix(df, decision_time, limit=None):
    """Select the same closed-candle prefix via a sorted timestamp index (O(log n))."""
    if df is None or df.empty:
        return df
    stop = int(df["close_time"].searchsorted(decision_time, side="right"))
    begin = max(0, stop - int(limit)) if limit is not None else 0
    return df.iloc[begin:stop]


def closed_prefix_self_test():
    """Binary-search prefix must match the old closed-candle mask/tail exactly."""
    times = pd.date_range("2026-01-01T00:00:00Z", periods=12, freq="1h")
    frame = pd.DataFrame({"close_time": times, "value": range(len(times))})
    cutoffs = [
        times[0] - pd.Timedelta(seconds=1),
        times[0],
        times[4] + pd.Timedelta(minutes=30),
        times[7],
        times[-1],
        times[-1] + pd.Timedelta(hours=1),
    ]
    for cutoff in cutoffs:
        for limit in (1, 3, 20):
            expected = frame[frame["close_time"] <= cutoff].tail(limit)
            actual = closed_prefix(frame, cutoff, limit)
            assert actual.reset_index(drop=True).equals(expected.reset_index(drop=True)), (
                f"closed-prefix mismatch at cutoff={cutoff}, limit={limit}"
            )
    assert closed_prefix(frame, times[0] - pd.Timedelta(seconds=1), 3).empty
    assert closed_prefix(pd.DataFrame(), times[-1], 3).empty
    print("CLOSED_PREFIX_SELF_TEST: PASS")
    return True


def historical_btc_regime(frames, decision_time):
    """Rebuild the engine BTC regime using only closed candles, without rescanning history."""
    latest = {}
    for tf in ("1h", "1d"):
        df = frames.get(tf)
        if df is None or df.empty:
            return None
        stop = int(df["close_time"].searchsorted(decision_time, side="right"))
        if stop <= 0:
            return None
        latest[tf] = main._btc_regime_from_row(df.iloc[stop - 1])
    h, d = latest["1h"], latest["1d"]
    if h["bullish"] and d["bullish"]:
        combined = "BULLISH"
    elif h["bearish"] and d["bearish"]:
        combined = "BEARISH"
    elif h["bearish"] and d["bullish"]:
        combined = "MIXED_BEARISH_1H"
    elif h["bullish"] and d["bearish"]:
        combined = "MIXED_BULLISH_1H"
    else:
        combined = "NEUTRAL"
    return {"combined": combined, "combined_score": h["score"] + d["score"], "1h": h, "daily": d}

def simulate_self_test():
    """Regression tests for same-candle stop/target ambiguity."""
    signal_time = pd.Timestamp("2026-10-01T00:00:00Z")
    entry_time = pd.Timestamp("2026-10-01T01:00:00Z")
    close_time = pd.Timestamp("2026-10-01T01:59:59.999000Z")
    candle = pd.DataFrame([{
        "open_time": entry_time, "close_time": close_time,
        "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0,
    }])
    trade, _ = simulate("TESTUSDT", "BUY", signal_time, 0, candle, 1.0, 95, "TEST",
                        {"entry": 100.0, "stop_loss": 98.0})
    assert trade is not None and trade["exit_reason"] == "TP1"
    assert abs(trade["exit"] - 103.6) < 1e-9, "same-candle TP1+TP2 must be credited as TP1"
    stop_conflict = candle.copy()
    stop_conflict.loc[0, "low"] = 97.0
    trade, _ = simulate("TESTUSDT", "BUY", signal_time, 0, stop_conflict, 1.0, 95, "TEST",
                        {"entry": 100.0, "stop_loss": 98.0})
    assert trade is not None and trade["exit_reason"] == "SL", "SL must win same-candle SL/TP conflict"
    print("HISTORICAL_EXIT_AMBIGUITY_SELF_TEST: PASS")
    return True


def run():
    # Fixed UTC end lets baseline and experiment use identical closed-candle windows.
    end_raw = os.getenv("BACKTEST_END_TIME", "").strip()
    if end_raw:
        end = pd.Timestamp(end_raw)
        if end.tzinfo is None:
            raise ValueError("BACKTEST_END_TIME must include Z or an explicit UTC offset")
        end = end.tz_convert("UTC").floor("h")
        if end > pd.Timestamp.now(tz="UTC").floor("h"):
            raise ValueError("BACKTEST_END_TIME cannot be in the future")
    else:
        end = pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=DAYS); fetch_start=start-pd.Timedelta(days=WARMUP_DAYS)
    trades=[]; engine_candidate_trades={}; errors=[]; diagnostics={"evaluated":0,"no_signal":0,"signals_before_execution":0,"signals_rejected_anti_chase":0,"first_no_signal_reasons":[]}
    perf={"stage_seconds":{},"counters":{"candle_steps":0,"timeframe_index_lookups":0,"rows_materialized":0,"btc_regime_lookups":0,"engine_calls":0}}
    # ENGINE_INTERNAL_PROFILE: profile exactly one real production-engine invocation.
    # This is offline-only instrumentation; no signal, score, or trade decision is changed.
    profile_enabled=os.getenv("BACKTEST_PROFILE_ENGINE","1").strip().lower() not in ("0","false","no","off")
    profile_every=max(1,int(os.getenv("BACKTEST_PROFILE_EVERY","100")))
    profiler=cProfile.Profile()
    engine_profile={"enabled":profile_enabled,"sample_every_calls":profile_every,"profiled_calls":0,"profiled_symbol":None,"profiled_time":None,"top_cumulative":[],"top_self_time":[]}
    def stage_done(name, started):
        perf["stage_seconds"][name]=perf["stage_seconds"].get(name,0.0)+(time.perf_counter()-started)
    print(f"PERIOD {start} -> {end}; symbols={SYMBOLS}; fee/side={FEE_BPS}bps; slippage/side={SLIPPAGE_BPS}bps",flush=True)
    # Fetch BTC context once and rebuild it at each historical decision instant.
    try:
        btc_raw={tf:fetch("BTCUSDT",tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000),include_boundary_open=(tf=="1h")) for tf in ("1h","1d")}
        t_prepare=time.perf_counter()
        btc_frames={tf:prepare(df) for tf,df in btc_raw.items()}
        stage_done("prepare_btc_history", t_prepare)
        if btc_frames["1h"].empty or btc_frames["1d"].empty:
            raise RuntimeError("BTC historical context unavailable")
        validate_warmup(btc_frames, start, "BTCUSDT", ("1h", "1d"))
        print(f"BTC historical context loaded; warm-up={WARMUP_DAYS}d",flush=True)
    except Exception as exc:
        errors.append({"symbol":"BTCUSDT","error":f"BTC context: {exc}"})
        btc_frames={"1h":pd.DataFrame(),"1d":pd.DataFrame()}
    for sym in SYMBOLS:
        try:
            print("FETCH",sym,flush=True)
            raw={}
            for tf in ("1h","30m","4h","1d"):
                if tf == "1h":
                    # Signal generation ends at end; fetch later closed candles for outcomes.
                    outcome_end_ms=int((end+pd.Timedelta(hours=73)).timestamp()*1000)
                    raw[tf]=fetch(sym,tf,int(fetch_start.timestamp()*1000),outcome_end_ms,
                                  include_boundary_open=True,signal_boundary_ms=int(end.timestamp()*1000))
                else:
                    raw[tf]=fetch(sym,tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000))
            if len(raw["1h"])<250 or len(raw["30m"])<50: raise RuntimeError("Insufficient historical candles")
            t_prepare=time.perf_counter()
            frames={tf:prepare(d) for tf,d in raw.items()}
            stage_done("prepare_symbol_history", t_prepare)
            validate_warmup(frames, start, sym)
            h1=frames["1h"]
            validate_boundary_execution_candle(h1, end)
            idx=max(220,int(h1.open_time.searchsorted(start)))
            baseline_last_exit=idx-1
            engine_last_exit={}
            for i in replay_signal_indices(h1, idx, end):
                t_step=time.perf_counter()
                c=h1.iloc[i]; close_time=c.close_time
                if close_time<start: continue
                perf["counters"]["candle_steps"] += 1
                data={}
                for tf,df in frames.items():
                    if not df.empty:
                        stop=int(df["close_time"].searchsorted(close_time, side="right"))
                        begin=max(0,stop-TIMEFRAME_LIMITS[tf])
                        data[tf]=df.iloc[begin:stop].copy()
                        perf["counters"]["timeframe_index_lookups"] += 1
                        perf["counters"]["rows_materialized"] += len(data[tf])
                    else:
                        data[tf]=None
                stage_done("closed_candle_selection", t_step)
                if len(data["1h"])<50 or len(data["30m"])<30: continue
                t_btc=time.perf_counter()
                btc_regime=historical_btc_regime(btc_frames,close_time)
                perf["counters"]["btc_regime_lookups"] += 1
                stage_done("btc_regime", t_btc)
                if btc_regime is None:
                    errors.append({"symbol":sym,"time":str(close_time),"error":"BTC historical regime unavailable"})
                    continue
                diagnostics["evaluated"] += 1
                # Evaluate every closed candle. The baseline and each engine counterfactual
                # maintain separate exit clocks so one engine's open trade cannot suppress
                # another engine's candidate stream.
                original_prepare=main.prepare_symbol_data
                original_live_price=main.get_live_price
                try:
                    main.prepare_symbol_data=lambda _symbol, _data=data: _data
                    current_price=float(data["1h"].iloc[-1]["close"])
                    current_close_time=str(data["1h"].iloc[-1]["close_time"])
                    main.get_live_price=lambda _symbol, _price=current_price, _time=current_close_time: {
                        "price":_price,"fetched_at":_time,"request_latency_seconds":0.0,"source":"historical closed candle"
                    }
                    t_engine=time.perf_counter()
                    if profile_enabled and (perf["counters"]["engine_calls"] + 1) % profile_every == 0:
                        profiler.enable()
                        scan=main.analyze_one_symbol(sym,btc_regime)
                        profiler.disable()
                        engine_profile["profiled_calls"] += 1
                        engine_profile["profiled_symbol"]=sym
                        engine_profile["profiled_time"]=str(close_time)
                        stats=pstats.Stats(profiler)
                        def profile_rows(sort_key, limit=40):
                            stats.sort_stats(sort_key)
                            rows=[]
                            for (filename,line_no,func_name),(primitive,total,ttotal,ctotal,callers) in list(stats.stats.items()):
                                rows.append({"function":func_name,"file":filename,"line":line_no,
                                             "calls":int(total),"primitive_calls":int(primitive),
                                             "self_seconds":round(float(ttotal),6),
                                             "cumulative_seconds":round(float(ctotal),6)})
                            rows.sort(key=lambda row: row["cumulative_seconds" if sort_key=="cumulative" else "self_seconds"],reverse=True)
                            return rows[:limit]
                        engine_profile["top_cumulative"]=profile_rows("cumulative")
                        engine_profile["top_self_time"]=profile_rows("tottime")
                        (OUT/"engine-profile.txt").write_text(
                            "PROFILED FIRST ENGINE CALL\\n"+stats.sort_stats("cumulative").stream.getvalue()
                            if False else "", encoding="utf-8")
                        buf=io.StringIO()
                        stats.stream=buf
                        stats.sort_stats("cumulative").print_stats(60)
                        (OUT/"engine-profile.txt").write_text(buf.getvalue(),encoding="utf-8")
                        (OUT/"engine-profile.json").write_text(json.dumps(engine_profile,indent=2),encoding="utf-8")
                    else:
                        scan=main.analyze_one_symbol(sym,btc_regime)
                    stage_done("signal_engine", t_engine)
                    perf["counters"]["engine_calls"] += 1
                except Exception as exc:
                    errors.append({"symbol":sym,"time":str(close_time),"error":f"production pipeline: {exc}"})
                    continue
                finally:
                    main.prepare_symbol_data=original_prepare
                    main.get_live_price=original_live_price
                selected=scan.get("signal") if isinstance(scan,dict) else None
                higher=scan.get("higher_signals",[]) if isinstance(scan,dict) else []
                candidates=[x for x in [selected]+(higher if isinstance(higher,list) else []) if isinstance(x,dict) and str(x.get("signal","")).upper() in ("BUY","SELL")]
                if not candidates:
                    diagnostics["no_signal"] += 1
                    trace=(scan.get("symbol_trace",{}) if isinstance(scan,dict) else {}) or {}
                    if len(diagnostics["first_no_signal_reasons"]) < 12:
                        diagnostics["first_no_signal_reasons"].append({"symbol":sym,"time":str(close_time),"first_rejection":trace.get("first_rejection"),"final_rejection":trace.get("final_rejection"),"error":scan.get("error") if isinstance(scan,dict) else "invalid scan result"})
                    continue

                # Build independent candidate streams: choose the strongest candidate
                # within each engine at this timestamp, not one global winner. This avoids
                # contaminating TREND-vs-REVERSAL results with cross-engine selection bias.
                by_engine={}
                for candidate in candidates:
                    engine_name=str(candidate.get("engine",candidate.get("signal_mode","UNKNOWN"))).upper()
                    previous=by_engine.get(engine_name)
                    rank=(float(candidate.get("professional_quality_score",0) or 0),
                          float(candidate.get("score",0) or 0),
                          1 if candidate.get("strength")=="STRONG" else 0)
                    if previous is None or rank>previous[0]:
                        by_engine[engine_name]=(rank,candidate)
                for engine_name,(_,engine_candidate) in by_engine.items():
                    if i <= engine_last_exit.get(engine_name,idx-1):
                        continue
                    engine_side=str(engine_candidate.get("signal","NO_SIGNAL")).upper()
                    engine_trade,engine_exit_i=simulate(
                        sym,engine_side,c.open_time,i+1,h1,float(c.get("atr",0) or 0),
                        engine_candidate.get("score",0),engine_candidate.get("strength",""),engine_candidate
                    )
                    if engine_trade:
                        engine_trade["engine"]=engine_name
                        engine_trade["signal_mode"]=engine_candidate.get("signal_mode","UNKNOWN")
                        engine_trade["btc_regime"]=btc_regime.get("combined","UNKNOWN")
                        engine_trade.update(signal_diagnostics(data["1h"],engine_side))
                        engine_candidate_trades.setdefault(engine_name,[]).append(engine_trade)
                        engine_last_exit[engine_name]=engine_exit_i

                # Primary baseline remains the production-style single strongest candidate.
                if i <= baseline_last_exit:
                    continue
                result=max(candidates,key=lambda x:(float(x.get("professional_quality_score",0) or 0),float(x.get("score",0) or 0),1 if x.get("strength")=="STRONG" else 0))
                side=str(result.get("signal","NO_SIGNAL")).upper()
                diagnostics["signals_before_execution"] += 1
                # Anti-chase remains diagnostic-only and cannot veto the baseline.
                location_diag=signal_diagnostics(data["1h"],side)
                trade,exit_i=simulate(sym,side,c.open_time,i+1,h1,float(c.get("atr",0) or 0),result.get("score",0),result.get("strength",""),result)
                if trade:
                    trade.update(location_diag)
                    trade["engine"]=str(result.get("engine",result.get("signal_mode","UNKNOWN"))).upper()
                    trade["signal_mode"]=result.get("signal_mode","UNKNOWN")
                    trade["btc_regime"]=btc_regime.get("combined","UNKNOWN")
                    trades.append(trade); baseline_last_exit=exit_i
                    print(f"TRADE {sym} {side} {trade['signal_time']} engine={trade['engine']} net={trade['net_pct']}% {trade['exit_reason']}",flush=True)
        except Exception as exc:
            errors.append({"symbol":sym,"error":str(exc)}); print("ERROR",sym,exc,flush=True)
    columns=["symbol","side","signal_time","entry_time","entry","stop_loss","tp1","tp2","exit_time","exit","exit_reason","gross_pct","cost_pct","net_pct","bars_held","score","strength","btc_regime","engine","signal_mode","signal_close","signal_atr","atr_pct","rsi","adx","volume_ratio","ema21_extension_atr","room_to_obstacle_atr","directional_move_6h_pct","directional_move_12h_pct","directional_move_24h_pct","range_position_20","entry_guard_allowed","entry_guard_reason"]
    pd.DataFrame(trades,columns=columns).to_csv(OUT/"trades.csv",index=False)
    vals=[float(t["net_pct"]) for t in trades]
    portfolio_ledger_self_test(OUT)
    initial_capital=float(os.getenv("BACKTEST_INITIAL_CAPITAL_USDT","1000"))
    risk_pct=float(os.getenv("BACKTEST_RISK_PCT","1.0"))
    max_position_pct=float(os.getenv("BACKTEST_MAX_POSITION_PCT","100"))
    portfolio=portfolio_ledger(trades,OUT,initial_cash=initial_capital,risk_pct=risk_pct,max_position_pct=max_position_pct)
    # Offline-only counterfactuals: replay each engine's candidate stream in its own
    # shared-cash account. These are diagnostic comparisons, not live filters.
    engine_portfolios={}
    for engine_name in sorted(engine_candidate_trades):
        engine_trades=engine_candidate_trades[engine_name]
        engine_out=OUT/"engine-comparison"/engine_name.lower()
        engine_portfolios[engine_name]=portfolio_ledger(
            engine_trades,engine_out,initial_cash=initial_capital,
            risk_pct=risk_pct,max_position_pct=max_position_pct
        )
    # Run a separate, explicitly experimental comparison. The baseline remains unchanged;
    # this does not activate the obstacle guard in main.py or the live Telegram scanner.
    guarded_trades=[t for t in trades if bool(t.get("entry_guard_allowed",True))]
    guard_portfolio=portfolio_ledger(guarded_trades,OUT/"entry-location-guard",initial_cash=initial_capital,risk_pct=risk_pct,max_position_pct=max_position_pct)
    guard_comparison={"rule":"nearest obstacle in previous 20 closed 1H candles must be at least 0.80 ATR away","baseline_candidate_trades":len(trades),"guard_candidate_trades":len(guarded_trades),"filtered_candidate_trades":len(trades)-len(guarded_trades),"status":"EXPERIMENTAL_COMPARISON_ONLY; not enabled in live engine"}
    perf["stage_seconds"]={k:round(v,4) for k,v in perf["stage_seconds"].items()}
    (OUT/"engine-profile.json").write_text(json.dumps(engine_profile,indent=2),encoding="utf-8")
    perf["total_instrumented_seconds"]=round(sum(perf["stage_seconds"].values()),4)
    # Linux GitHub-hosted runners report ru_maxrss in KiB; diagnostics only.
    perf["peak_rss_kib"]=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    summary={"performance":perf,"status":"COMPLETED_WITH_ERRORS" if errors else "COMPLETED","period_start":str(start),"period_end":str(end),"days":DAYS,"symbols":SYMBOLS,"candidate_trade_count":len(trades),"candidate_win_rate_pct":round(sum(v>0 for v in vals)/len(vals)*100,2) if vals else None,"naive_gross_return_sum_pct_not_portfolio":round(sum(t["gross_pct"] for t in trades),4),"naive_net_return_sum_pct_not_portfolio":round(sum(vals),4),"average_net_candidate_trade_pct":round(sum(vals)/len(vals),4) if vals else None,"candidate_profit_factor":round(sum(v for v in vals if v>0)/abs(sum(v for v in vals if v<0)),3) if any(v<0 for v in vals) else None,"exit_reasons_candidates":{k:sum(t["exit_reason"]==k for t in trades) for k in sorted({t["exit_reason"] for t in trades})},"portfolio":portfolio,"engine_only_portfolio_comparison":engine_portfolios,"portfolio_entry_location_guard":guard_portfolio,"entry_location_guard_comparison":guard_comparison,"assumptions":{"entry":"next 1H candle open after signal candle closes","exit_timestamp":"exit candle close timestamp for conservative portfolio event ordering","stop":"engine stop distance re-anchored to next 1H open; fallback 1.5 ATR","targets":"engine TP1_RR/TP2_RR; first touched target exits full position","same_candle_conflict":"SL first; TP1 before TP2 when both targets are touched in one candle","costs":"fee and slippage on both entry and exit included in net P/L","capital":"single shared cash ledger; no leverage; 1% equity risk per accepted trade; max position capped at 100% of equity and available cash","overlap":"concurrent trades compete for free cash; one position per symbol","drawdown":"portfolio equity marked-to-market at historical hourly closes including open positions","btc_regime":"Historical BTC 1H and Daily regime rebuilt from closed candles at each decision time","indicator_warmup":f"{WARMUP_DAYS} calendar days fetched before test start; >= {WARMUP_BARS} closed pre-test candles required per timeframe; each decision uses the latest configured 250 candles","experimental_filter":"DISABLED in primary baseline; EMA21 extension is diagnostic-only and does not veto production-engine candidates","entry_location_guard":"Separate comparison only; requires at least 0.80 ATR room to the nearest confirmed 2-left/2-right swing obstacle in the previous 20 closed 1H candles; no confirmed directional obstacle means no veto; not active in baseline/live engine","naive_returns_warning":"sum of individual trade percentages is not portfolio return and is shown only for comparison"},"engine_breakdown":{k:{"candidate_trades":len(v),"naive_net_return_sum_pct_not_portfolio":round(sum(float(t["net_pct"]) for t in v),4)} for k,v in sorted(engine_candidate_trades.items())},"diagnostics":diagnostics,"errors":errors}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8"); print(json.dumps(summary,indent=2),flush=True)
    if not trades: raise SystemExit("No trades produced; do not infer profitability.")
if __name__=="__main__": run()
