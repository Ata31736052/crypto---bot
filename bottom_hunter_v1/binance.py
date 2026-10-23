"""Minimal public-data client for Binance Spot; never sends orders."""
from __future__ import annotations

import time
import requests

BASE_URL = "https://api.binance.com"


def fetch_closed_klines(symbol: str, interval: str = "1h", limit: int = 100) -> list[dict]:
    if limit < 30 or limit > 1000:
        raise ValueError("limit must be between 30 and 1000")
    response = requests.get(
        f"{BASE_URL}/api/v3/klines",
        params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    now_ms = int(time.time() * 1000)
    candles = []
    for row in payload:
        close_time = int(row[6])
        if close_time >= now_ms:
            continue
        candles.append({
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "close_time": close_time,
        })
    return candles
