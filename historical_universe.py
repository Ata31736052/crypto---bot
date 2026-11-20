"""Point-in-time Binance Spot USDT universe from Binance Vision hourly archives.

Each snapshot is taken at an hourly decision boundary and uses only the 24
fully closed 1h candles ending at that boundary. The archive contains historical
and delisted symbols; current exchangeInfo is never used for historical ranking.
"""
from __future__ import annotations

import io
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

S3_LIST_URL = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
VISION_URL = "https://data.binance.vision"
MONTHLY_SYMBOL_PREFIX = "data/spot/monthly/klines/"
DAILY_SYMBOL_PREFIX = "data/spot/daily/klines/"
ONE_HOUR = pd.Timedelta(hours=1)
KLINE_COLUMNS = [
    "open_ms", "open", "high", "low", "close", "volume", "close_ms",
    "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
]


def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _list_symbols_for_prefix(prefix, session=None, timeout=30):
    client = session or requests
    token = None
    symbols = set()
    while True:
        params = {"list-type": "2", "prefix": prefix, "delimiter": "/", "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        response = client.get(S3_LIST_URL, params=params, timeout=timeout)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        next_token = None
        truncated = False
        for node in root.iter():
            name = _local_name(node.tag)
            if name == "Prefix" and node.text:
                value = node.text.strip()
                if value.startswith(prefix):
                    symbol = value[len(prefix):].strip("/")
                    if re.fullmatch(r"[A-Z0-9_]{1,30}USDT", symbol):
                        symbols.add(symbol)
            elif name == "NextContinuationToken":
                next_token = node.text
            elif name == "IsTruncated":
                truncated = (node.text or "").strip().lower() == "true"
        if not truncated:
            break
        if not next_token or next_token == token:
            raise RuntimeError(f"Binance Vision S3 listing pagination stalled for {prefix}")
        token = next_token
    return symbols


def list_historical_spot_symbols(session=None, timeout=30):
    """Enumerate historical monthly Spot symbols, including delisted pairs."""
    symbols = _list_symbols_for_prefix(MONTHLY_SYMBOL_PREFIX, session=session, timeout=timeout)
    if not symbols:
        raise RuntimeError("Binance Vision monthly Spot symbol listing returned no USDT pairs")
    return sorted(symbols)


def list_daily_spot_symbols(session=None, timeout=30):
    """Enumerate symbols with daily archive folders (new listings before monthly publication)."""
    return sorted(_list_symbols_for_prefix(DAILY_SYMBOL_PREFIX, session=session, timeout=timeout))


def month_keys(start, end):
    """Return YYYY-MM keys overlapping [start, end], inclusive."""
    first = pd.Timestamp(start).tz_convert("UTC").to_period("M")
    last = pd.Timestamp(end).tz_convert("UTC").to_period("M")
    return [str(period) for period in pd.period_range(first, last, freq="M")]


def _read_hourly_archive(content, symbol, month):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise RuntimeError(f"{symbol} 1h {month}: expected one CSV in archive, found {len(names)}")
            frame = pd.read_csv(
                archive.open(names[0]), header=None, usecols=[0, 7],
                names=["open_ms", "quote_volume"],
            )
    except (zipfile.BadZipFile, pd.errors.ParserError, ValueError) as exc:
        raise RuntimeError(f"{symbol} 1h {month}: corrupt/unreadable Binance Vision archive: {exc}") from exc
    if frame.empty:
        return pd.DataFrame(columns=["open_time", "quote_volume"])
    frame["open_ms"] = pd.to_numeric(frame["open_ms"], errors="coerce")
    frame["quote_volume"] = pd.to_numeric(frame["quote_volume"], errors="coerce")
    frame = frame.dropna(subset=["open_ms", "quote_volume"])
    if frame.empty:
        return pd.DataFrame(columns=["open_time", "quote_volume"])
    # Spot archive timestamps switched from milliseconds to microseconds in 2025.
    unit = "us" if float(frame["open_ms"].max()) >= 10**14 else "ms"
    frame["open_time"] = pd.to_datetime(frame["open_ms"], unit=unit, utc=True)
    if (frame["quote_volume"] < 0).any():
        raise RuntimeError(f"{symbol} 1h {month}: negative quote volume in archive")
    return frame[["open_time", "quote_volume"]].groupby("open_time", as_index=False).sum()


def _read_archive_zip(content, symbol, key):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise RuntimeError(f"{symbol} 1h {key}: expected one CSV in archive, found {len(names)}")
            frame = pd.read_csv(
                archive.open(names[0]), header=None, usecols=[0, 7],
                names=["open_ms", "quote_volume"],
            )
    except (zipfile.BadZipFile, pd.errors.ParserError, ValueError) as exc:
        raise RuntimeError(f"{symbol} 1h {key}: corrupt/unreadable Binance Vision archive: {exc}") from exc
    if frame.empty:
        return pd.DataFrame(columns=["open_time", "quote_volume"])
    frame["open_ms"] = pd.to_numeric(frame["open_ms"], errors="coerce")
    frame["quote_volume"] = pd.to_numeric(frame["quote_volume"], errors="coerce")
    frame = frame.dropna(subset=["open_ms", "quote_volume"])
    if frame.empty:
        return pd.DataFrame(columns=["open_time", "quote_volume"])
    unit = "us" if float(frame["open_ms"].max()) >= 10**14 else "ms"
    frame["open_time"] = pd.to_datetime(frame["open_ms"], unit=unit, utc=True)
    if (frame["quote_volume"] < 0).any():
        raise RuntimeError(f"{symbol} 1h {key}: negative quote volume in archive")
    return frame[["open_time", "quote_volume"]].groupby("open_time", as_index=False).sum()


def _download_hourly_month(
    symbol, month, cache_dir, allow_daily_fallback=False,
    daily_start=None, daily_end=None, timeout=45,
):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol}-1h-{month}.zip"
    if path.exists() and path.stat().st_size:
        return _read_archive_zip(path.read_bytes(), symbol, month)
    url = f"{VISION_URL}/data/spot/monthly/klines/{symbol}/1h/{symbol}-1h-{month}.zip"
    response = requests.get(url, timeout=timeout)
    if response.status_code == 404:
        if not allow_daily_fallback or daily_start is None or daily_end is None:
            return pd.DataFrame(columns=["open_time", "quote_volume"])
        month_start = pd.Timestamp(f"{month}-01", tz="UTC")
        month_end = month_start + pd.offsets.MonthEnd(0)
        first_day = max(month_start, pd.Timestamp(daily_start).tz_convert("UTC").floor("D"))
        last_day = min(month_end, pd.Timestamp(daily_end).tz_convert("UTC").floor("D"))
        if first_day > last_day:
            return pd.DataFrame(columns=["open_time", "quote_volume"])
        daily_frames = []
        for day in pd.date_range(first_day, last_day, freq="D", tz="UTC"):
            day_key = day.strftime("%Y-%m-%d")
            daily_path = cache_dir / f"{symbol}-1h-{day_key}.zip"
            if daily_path.exists() and daily_path.stat().st_size:
                daily_frames.append(_read_archive_zip(daily_path.read_bytes(), symbol, day_key))
                continue
            daily_url = f"{VISION_URL}/data/spot/daily/klines/{symbol}/1h/{symbol}-1h-{day_key}.zip"
            daily_response = requests.get(daily_url, timeout=timeout)
            if daily_response.status_code == 404:
                continue
            daily_response.raise_for_status()
            parsed = _read_archive_zip(daily_response.content, symbol, day_key)
            temp = daily_path.with_suffix(".zip.tmp")
            temp.write_bytes(daily_response.content)
            temp.replace(daily_path)
            daily_frames.append(parsed)
        if not daily_frames:
            return pd.DataFrame(columns=["open_time", "quote_volume"])
        return pd.concat(daily_frames, ignore_index=True).drop_duplicates("open_time").sort_values("open_time")
    response.raise_for_status()
    parsed = _read_archive_zip(response.content, symbol, month)
    temp = path.with_suffix(".zip.tmp")
    temp.write_bytes(response.content)
    temp.replace(path)
    return parsed


def _hourly_rolling_quote_volume(frame, snapshot_times):
    """Return only complete, gap-free trailing 24-closed-hour quote-volume windows."""
    if frame is None or frame.empty:
        return pd.Series(dtype="float64")
    data = frame[["open_time", "quote_volume"]].copy()
    data["open_time"] = pd.to_datetime(data["open_time"], utc=True)
    data["quote_volume"] = pd.to_numeric(data["quote_volume"], errors="coerce")
    data = data.dropna().drop_duplicates("open_time", keep="last").sort_values("open_time")
    if data.empty or (data["quote_volume"] < 0).any():
        return pd.Series(dtype="float64")
    index = pd.DatetimeIndex(data["open_time"])
    values = pd.Series(data["quote_volume"].astype(float).to_numpy(), index=index)
    rolling = values.rolling(window=24, min_periods=24).sum()
    consecutive = pd.Series(index.to_series().diff().eq(ONE_HOUR).to_numpy(), index=index)
    gap_free = consecutive.rolling(window=23, min_periods=23).sum().eq(23)
    rolling = rolling[gap_free & rolling.notna()]
    # A 1h candle opened at t becomes usable at the next hour boundary.
    rolling.index = rolling.index + ONE_HOUR
    return rolling[rolling.index.isin(snapshot_times)]


def build_point_in_time_universe(
    start,
    end,
    min_quote_volume_usdt=5_000_000,
    max_symbols=100,
    cache_dir=".cache/binance-vision-hourly",
    symbols=None,
    max_workers=16,
    session=None,
    is_directional_base=None,
    excluded_base_assets=("BTC",),
):
    """Build hourly top-N snapshots using the previous 24 closed 1h quote-volume bars.

    Listing history is inferred from Binance Vision's historical Spot archive,
    which includes delisted pairs. A symbol only qualifies when all 24 hourly
    candles exist consecutively and its rolling quote volume meets the threshold.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    start, end = start.tz_convert("UTC"), end.tz_convert("UTC")
    if end <= start:
        raise ValueError("end must be after start")
    if min_quote_volume_usdt < 0 or max_symbols < 1:
        raise ValueError("invalid historical universe limits")

    if symbols is not None:
        all_symbols = list(symbols)
        daily_symbols = set()
    else:
        monthly_symbols = set(list_historical_spot_symbols(session=session))
        daily_symbols = set(list_daily_spot_symbols(session=session))
        all_symbols = sorted(monthly_symbols | daily_symbols)
    excluded = set(excluded_base_assets)
    candidates = sorted({
        str(symbol).upper().replace("/", "").replace("-", "")
        for symbol in all_symbols
        if str(symbol).upper().replace("/", "").replace("-", "").endswith("USDT")
        and str(symbol).upper().replace("/", "").replace("-", "")[:-4] not in excluded
        and (
            is_directional_base is None
            or is_directional_base(str(symbol).upper().replace("/", "").replace("-", "")[:-4])
        )
    })
    if not candidates:
        raise RuntimeError("Historical archive contained no eligible directional USDT Spot symbols")

    # A signal candle closing at t-1ms is acted on at boundary t. The universe
    # at t uses the 24 candles whose opens are [t-24h, t-1h].
    first_snapshot = start.floor("h") + ONE_HOUR
    last_snapshot = end.floor("h")
    snapshot_times = pd.date_range(first_snapshot, last_snapshot, freq="h", tz="UTC")
    if snapshot_times.empty:
        raise RuntimeError("No hourly universe snapshots fall inside the requested replay window")
    volume_start = snapshot_times[0] - pd.Timedelta(hours=24)
    volume_end = snapshot_times[-1] - ONE_HOUR
    months = month_keys(volume_start, volume_end)

    frames_by_symbol = {}
    failures = []
    current_month = pd.Timestamp.now(tz="UTC").strftime("%Y-%m")
    tasks = [(symbol, month) for symbol in candidates for month in months]
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        future_map = {
            pool.submit(
                _download_hourly_month, symbol, month, cache_dir,
                allow_daily_fallback=(symbol in daily_symbols and month == current_month),
                daily_start=volume_start, daily_end=volume_end,
            ): (symbol, month)
            for symbol, month in tasks
        }
        for future in as_completed(future_map):
            symbol, month = future_map[future]
            try:
                frame = future.result()
            except Exception as exc:
                failures.append({"symbol": symbol, "month": month, "error": str(exc)})
                continue
            if not frame.empty:
                frames_by_symbol.setdefault(symbol, []).append(frame)

    if failures:
        raise RuntimeError(
            f"Historical hourly universe archive download incomplete: {len(failures)} failures; "
            f"sample={failures[:10]}"
        )

    candidates_by_time = {}
    symbols_with_usable_windows = set()
    for symbol, pieces in frames_by_symbol.items():
        combined = pd.concat(pieces, ignore_index=True).drop_duplicates("open_time", keep="last")
        rolling = _hourly_rolling_quote_volume(combined, snapshot_times)
        if rolling.empty:
            continue
        symbols_with_usable_windows.add(symbol)
        for decision_time, quote_volume in rolling.items():
            if float(quote_volume) >= float(min_quote_volume_usdt):
                candidates_by_time.setdefault(decision_time, []).append((symbol, float(quote_volume)))

    hourly_snapshots = {}
    selected_union = set()
    hourly_counts = []
    for snapshot_time in snapshot_times:
        ranked = candidates_by_time.get(snapshot_time, [])
        ranked.sort(key=lambda item: (-item[1], item[0]))
        chosen = ranked[:int(max_symbols)]
        key = snapshot_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        hourly_snapshots[key] = [symbol for symbol, _ in chosen]
        selected_union.update(hourly_snapshots[key])
        hourly_counts.append({
            "snapshot_time_utc": key,
            "volume_window_start_utc": (snapshot_time - pd.Timedelta(hours=24)).isoformat(),
            "volume_window_end_utc": (snapshot_time - ONE_HOUR).isoformat(),
            "eligible_above_threshold": len(ranked),
            "selected_count": len(chosen),
            "symbols": [{"symbol": symbol, "quote_volume_usdt": round(volume, 8)} for symbol, volume in chosen],
        })

    if not selected_union:
        raise RuntimeError("Historical point-in-time hourly universe is empty for the requested period")
    return {
        "symbols": sorted(selected_union),
        "hourly_snapshots": hourly_snapshots,
        "hourly_counts": hourly_counts,
        "source": "Binance Vision historical Spot monthly/daily 1h kline archives",
        "selection_method": "previous_24_closed_1h_quote_volume_ranked_at_each_hour",
        "snapshot_cadence": "hourly_at_next_1h_open",
        "min_quote_volume_usdt": float(min_quote_volume_usdt),
        "max_symbols_per_snapshot": int(max_symbols),
        "candidate_symbol_count": len(candidates),
        "symbols_with_usable_24h_windows": len(symbols_with_usable_windows),
        "selected_union_count": len(selected_union),
        "archive_failures": 0,
        "historical_point_in_time": True,
        "lookahead_free": True,
        "known_limitations": [
            "Historical tradability is inferred from Binance Vision archived hourly candles, not archived exchangeInfo status snapshots.",
            "A symbol must have 24 consecutive archived hourly candles; any missing hour invalidates that 24h volume window.",
            "Temporary trading halts or archive gaps can make a pair ineligible even if Binance status was TRADING.",
            "The archive is Binance's historical data source and includes delisted symbols, avoiding selection from today's active-symbol list.",
        ],
    }
