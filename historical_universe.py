"""Point-in-time Binance Spot USDT universe from historical public kline archives.

Universe snapshots are made at 00:00 UTC from the previous fully closed UTC
1d candle's quote-asset volume. This is deliberately a daily snapshot cadence;
the signal engine itself continues to evaluate every closed 1h candle.
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
SYMBOL_PREFIX = "data/spot/monthly/klines/"
KLINE_COLUMNS = [
    "open_ms", "open", "high", "low", "close", "volume", "close_ms",
    "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
]


def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def list_historical_spot_symbols(session=None, timeout=30):
    """Enumerate symbol directories in Binance Vision's historical Spot archive."""
    client = session or requests
    token = None
    symbols = set()
    while True:
        params = {
            "list-type": "2",
            "prefix": SYMBOL_PREFIX,
            "delimiter": "/",
            "max-keys": "1000",
        }
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
                if value.startswith(SYMBOL_PREFIX):
                    symbol = value[len(SYMBOL_PREFIX):].strip("/")
                    if re.fullmatch(r"[A-Z0-9_]{4,30}USDT", symbol):
                        symbols.add(symbol)
            elif name == "NextContinuationToken":
                next_token = node.text
            elif name == "IsTruncated":
                truncated = (node.text or "").strip().lower() == "true"
        if not truncated:
            break
        if not next_token or next_token == token:
            raise RuntimeError("Binance Vision S3 listing pagination stalled")
        token = next_token
    if not symbols:
        raise RuntimeError("Binance Vision historical Spot symbol listing returned no USDT pairs")
    return sorted(symbols)


def month_keys(start, end):
    """Return YYYY-MM keys overlapping [start, end], inclusive."""
    first = pd.Timestamp(start).tz_convert("UTC").to_period("M")
    last = pd.Timestamp(end).tz_convert("UTC").to_period("M")
    return [str(period) for period in pd.period_range(first, last, freq="M")]


def _read_daily_archive(content, symbol, month):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise RuntimeError(f"{symbol} 1d {month}: expected one CSV in archive, found {len(names)}")
            frame = pd.read_csv(archive.open(names[0]), header=None, usecols=[0, 7], names=["open_ms", "quote_volume"])
    except (zipfile.BadZipFile, pd.errors.ParserError, ValueError) as exc:
        raise RuntimeError(f"{symbol} 1d {month}: corrupt/unreadable Binance Vision archive: {exc}") from exc
    if frame.empty:
        return pd.DataFrame(columns=["day", "quote_volume"])
    frame["open_ms"] = pd.to_numeric(frame["open_ms"], errors="coerce")
    frame["quote_volume"] = pd.to_numeric(frame["quote_volume"], errors="coerce")
    frame = frame.dropna(subset=["open_ms", "quote_volume"])
    if frame.empty:
        return pd.DataFrame(columns=["day", "quote_volume"])
    # Binance Spot archive timestamps changed from milliseconds to microseconds
    # starting 2025-01-01; magnitude detection handles both formats.
    unit = "us" if float(frame["open_ms"].max()) >= 10**14 else "ms"
    frame["day"] = pd.to_datetime(frame["open_ms"], unit=unit, utc=True).dt.floor("D")
    if (frame["quote_volume"] < 0).any():
        raise RuntimeError(f"{symbol} 1d {month}: negative quote volume in archive")
    return frame[["day", "quote_volume"]].groupby("day", as_index=False).sum()


def _download_daily_month(symbol, month, cache_dir, timeout=45):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{symbol}-1d-{month}.zip"
    if path.exists() and path.stat().st_size:
        return _read_daily_archive(path.read_bytes(), symbol, month)
    url = f"{VISION_URL}/data/spot/monthly/klines/{symbol}/1d/{symbol}-1d-{month}.zip"
    response = requests.get(url, timeout=timeout)
    if response.status_code == 404:
        return pd.DataFrame(columns=["day", "quote_volume"])
    response.raise_for_status()
    # Validate before caching so a truncated download cannot poison later runs.
    parsed = _read_daily_archive(response.content, symbol, month)
    temp = path.with_suffix(".zip.tmp")
    temp.write_bytes(response.content)
    temp.replace(path)
    return parsed


def build_point_in_time_universe(
    start,
    end,
    min_quote_volume_usdt=5_000_000,
    max_symbols=100,
    cache_dir=".cache/binance-vision",
    symbols=None,
    max_workers=16,
    session=None,
    is_directional_base=None,
    excluded_base_assets=("BTC",),
):
    """Build daily 00:00 UTC universe snapshots using only the previous UTC day's volume.

    Missing symbol/day candles are not carried forward: a pair must have an
    observed prior-day candle and meet the quote-volume threshold to qualify.
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    start, end = start.tz_convert("UTC"), end.tz_convert("UTC")
    if end < start:
        raise ValueError("end must not precede start")
    if min_quote_volume_usdt < 0 or max_symbols < 1:
        raise ValueError("invalid historical universe limits")

    all_symbols = list(symbols) if symbols is not None else list_historical_spot_symbols(session=session)
    candidates = sorted({
        str(symbol).upper().replace("/", "").replace("-", "")
        for symbol in all_symbols
        if str(symbol).upper().replace("/", "").replace("-", "").endswith("USDT")
    })
    excluded = set(excluded_base_assets)
    if is_directional_base:
        candidates = [
            symbol for symbol in candidates
            if is_directional_base(symbol[:-4]) and symbol[:-4] not in excluded
        ]
    else:
        candidates = [symbol for symbol in candidates if symbol[:-4] not in excluded]
    if not candidates:
        raise RuntimeError("Historical archive contained no eligible USDT Spot symbols")

    snapshots = pd.date_range(start=start.floor("D"), end=end.floor("D"), freq="D", tz="UTC")
    required_days = [day - pd.Timedelta(days=1) for day in snapshots]
    months = month_keys(min(required_days), max(required_days))

    daily_by_symbol = {}
    failures = []
    tasks = [(symbol, month) for symbol in candidates for month in months]
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
        future_map = {
            pool.submit(_download_daily_month, symbol, month, cache_dir): (symbol, month)
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
                daily_by_symbol.setdefault(symbol, []).append(frame)

    if failures:
        sample = failures[:10]
        raise RuntimeError(
            f"Historical universe archive download incomplete: {len(failures)} symbol-month failures; "
            f"sample={sample}"
        )

    volumes = {}
    for symbol, frames in daily_by_symbol.items():
        combined = pd.concat(frames, ignore_index=True).drop_duplicates("day", keep="last")
        volumes[symbol] = combined.set_index("day")["quote_volume"].to_dict()

    daily_snapshots = {}
    selected_union = set()
    daily_counts = []
    for snapshot_time in snapshots:
        volume_day = snapshot_time - pd.Timedelta(days=1)
        ranked = [
            (symbol, float(by_day[volume_day]))
            for symbol, by_day in volumes.items()
            if volume_day in by_day and float(by_day[volume_day]) >= float(min_quote_volume_usdt)
        ]
        ranked.sort(key=lambda item: (-item[1], item[0]))
        chosen = ranked[:int(max_symbols)]
        day_key = snapshot_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        daily_snapshots[day_key] = [symbol for symbol, _ in chosen]
        selected_union.update(daily_snapshots[day_key])
        daily_counts.append({
            "snapshot_time_utc": day_key,
            "volume_candle_day_utc": volume_day.strftime("%Y-%m-%d"),
            "eligible_above_threshold": len(ranked),
            "selected_count": len(chosen),
            "symbols": [{"symbol": symbol, "quote_volume_usdt": round(volume, 8)} for symbol, volume in chosen],
        })

    if not selected_union:
        raise RuntimeError("Historical point-in-time universe is empty for the requested period")
    return {
        "symbols": sorted(selected_union),
        "daily_snapshots": daily_snapshots,
        "daily_counts": daily_counts,
        "source": "Binance Vision historical Spot monthly 1d kline archives",
        "selection_method": "previous_closed_UTC_1d_quote_volume",
        "snapshot_cadence": "daily_at_00:00_UTC",
        "min_quote_volume_usdt": float(min_quote_volume_usdt),
        "max_symbols_per_snapshot": int(max_symbols),
        "candidate_symbol_count": len(candidates),
        "selected_union_count": len(selected_union),
        "archive_failures": 0,
        "historical_point_in_time": True,
        "lookahead_free": True,
        "known_limitations": [
            "Universe membership is sampled daily at 00:00 UTC, while signal evaluation remains hourly.",
            "Pairs need an archived prior-UTC-day candle to qualify; missing/no-trade days are not forward-filled.",
            "A pair must still pass the signal engine's 200-bar timeframe warm-up before it can be replayed.",
        ],
    }
