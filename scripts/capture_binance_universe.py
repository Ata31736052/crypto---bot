#!/usr/bin/env python3
"""Read-only Binance Spot universe snapshot. No signal, Telegram, or trading side effects."""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision").rstrip("/")
OUT = Path("universe-snapshots")
TIMEOUT = 30


def get_json(path):
    response = requests.get(f"{BASE}{path}", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def main():
    captured = datetime.now(timezone.utc)
    exchange = get_json("/api/v3/exchangeInfo")
    tickers = get_json("/api/v3/ticker/24hr")
    if not isinstance(exchange, dict) or not isinstance(exchange.get("symbols"), list):
        raise RuntimeError("Invalid exchangeInfo response")
    if not isinstance(tickers, list):
        raise RuntimeError("Invalid 24hr ticker response")

    ticker_by_symbol = {x.get("symbol"): x for x in tickers if isinstance(x, dict)}
    rows = []
    for item in exchange["symbols"]:
        symbol = item.get("symbol")
        ticker = ticker_by_symbol.get(symbol, {})
        rows.append({
            "symbol": symbol,
            "status": item.get("status"),
            "baseAsset": item.get("baseAsset"),
            "quoteAsset": item.get("quoteAsset"),
            "isSpotTradingAllowed": item.get("isSpotTradingAllowed"),
            "quoteVolume24h": ticker.get("quoteVolume"),
            "volume24h": ticker.get("volume"),
            "weightedAvgPrice24h": ticker.get("weightedAvgPrice"),
            "lastPrice": ticker.get("lastPrice"),
            "priceChangePercent24h": ticker.get("priceChangePercent"),
            "count24h": ticker.get("count"),
        })

    stamp = captured.strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "captured_at_utc": captured.isoformat(),
        "source": BASE,
        "endpoint_exchange_info": "/api/v3/exchangeInfo",
        "endpoint_ticker_24h": "/api/v3/ticker/24hr",
        "symbol_count": len(rows),
        "trading_spot_usdt_count": sum(
            1 for x in rows
            if x["status"] == "TRADING" and x["quoteAsset"] == "USDT"
            and x["isSpotTradingAllowed"] is True
        ),
        "symbols": rows,
    }
    json_path = OUT / f"universe-{stamp}.json"
    csv_path = OUT / f"universe-{stamp}.csv"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    # Fail closed if the capture is structurally incomplete.
    if payload["symbol_count"] < 100:
        raise RuntimeError(f"Suspiciously small exchangeInfo universe: {payload['symbol_count']}")
    eligible = [x for x in rows if x["status"] == "TRADING" and x["quoteAsset"] == "USDT"
                and x["isSpotTradingAllowed"] is True]
    if any(x["quoteVolume24h"] is None for x in eligible):
        raise RuntimeError("Missing 24h quote volume for one or more eligible USDT spot symbols")
    print(json.dumps({
        "captured_at_utc": payload["captured_at_utc"],
        "symbol_count": payload["symbol_count"],
        "trading_spot_usdt_count": payload["trading_spot_usdt_count"],
        "json": str(json_path),
        "csv": str(csv_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
