#!/usr/bin/env python3
"""Read-only reconstruction of Run #160 BOTTOM_HUNTER signal-time candle context."""
import csv, io, json, os, sys, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
import requests

REPO = "Ata31736052/crypto---bot"
RUN160_ARTIFACT_ID = 14102983195
API = "https://api.binance.com/api/v3/klines"
OUT = Path("diagnostic-output")
OUT.mkdir(exist_ok=True)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "run160-bottom-hunter-diagnostic/1.0"})

def utc_ms(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def download_original_trades():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to download Run #160 artifact")
    url = f"https://api.github.com/repos/{REPO}/actions/artifacts/{RUN160_ARTIFACT_ID}/zip"
    response = SESSION.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=90)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        candidates = [n for n in archive.namelist() if n.endswith("trades.csv")]
        if len(candidates) != 1:
            raise RuntimeError(f"Expected one trades.csv in artifact; found {candidates}")
        return list(csv.DictReader(io.TextIOWrapper(archive.open(candidates[0]), encoding="utf-8-sig")))

def get_klines(symbol, end_time_ms):
    params = {"symbol": symbol, "interval": "1h", "endTime": end_time_ms, "limit": 72}
    last_error = None
    for attempt in range(6):
        try:
            response = SESSION.get(API, params=params, timeout=30)
            if response.status_code in (418, 429):
                time.sleep(min(60, int(response.headers.get("Retry-After", 2 ** attempt))))
                continue
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise RuntimeError(f"Unexpected Binance response: {rows}")
            return rows
        except Exception as exc:
            last_error = exc
            if attempt == 5:
                break
            time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"Binance kline request failed: {last_error}")

def reconstruct(row):
    symbol = row["symbol"].strip().upper()
    signal_ms = utc_ms(row["signal_time"])
    entry_ms = utc_ms(row["entry_time"])
    if entry_ms - signal_ms != 3600000:
        raise RuntimeError(f"Unexpected signal/entry spacing: {row['signal_time']} -> {row['entry_time']}")
    klines = get_klines(symbol, entry_ms - 1)
    if len(klines) != 72:
        raise RuntimeError(f"Expected 72 hourly bars, got {len(klines)}")
    bars = [{"open_time": int(k[0]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])} for k in klines]
    if bars[-1]["open_time"] != signal_ms:
        raise RuntimeError(f"Signal candle mismatch: expected {signal_ms}, got {bars[-1]['open_time']}")
    signal_close = float(row["signal_close"])
    api_close = bars[-1]["close"]
    close_diff_pct = abs(api_close / signal_close - 1.0) * 100 if signal_close else None
    low_72, high_72 = min(b["low"] for b in bars), max(b["high"] for b in bars)
    dist_low = (signal_close / low_72 - 1.0) * 100 if low_72 > 0 else None

    # Exact parity with historical_backtest.py::signal_diagnostics prior = df.iloc[-21:-1].
    prior20 = bars[-21:-1]
    prior_highs, prior_lows = [b["high"] for b in prior20], [b["low"] for b in prior20]
    hi20, lo20 = max(prior_highs), min(prior_lows)
    range_position_20 = (signal_close - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5
    swing_highs = []
    for i in range(2, len(prior20) - 2):
        h = prior_highs[i]
        if h > max(prior_highs[i-2:i]) and h >= max(prior_highs[i+1:i+3]):
            swing_highs.append(h)
    resistance_levels = [level for level in swing_highs if level > signal_close]
    atr = float(row.get("signal_atr") or 0)
    if resistance_levels and atr > 0:
        nearest_resistance = min(resistance_levels)
        room_atr = (nearest_resistance - signal_close) / atr
        guard_allowed = room_atr >= 0.80
        guard_reason = f"ENTRY_LOCATION_SWING_ROOM_{room_atr:.2f}_ATR"
        resistance_distance_pct = (nearest_resistance / signal_close - 1.0) * 100
    else:
        nearest_resistance, room_atr, resistance_distance_pct = None, None, None
        guard_allowed, guard_reason = True, "ENTRY_LOCATION_NO_CONFIRMED_RESISTANCE"

    return {
        "symbol": symbol, "signal_time": row["signal_time"], "entry_time": row["entry_time"],
        "signal_close_csv": signal_close, "signal_close_binance": api_close,
        "signal_close_abs_diff_pct": close_diff_pct, "bars_retrieved": len(bars),
        "low_72h": low_72, "high_72h": high_72, "distance_from_72h_low_pct": dist_low,
        "within_4_5pct_of_72h_low": dist_low <= 4.5 if dist_low is not None else None,
        "within_7pct_of_72h_low": dist_low <= 7.0 if dist_low is not None else None,
        "range_position_20_rebuilt": range_position_20,
        "range_position_20_run160": float(row.get("range_position_20") or 0),
        "nearest_confirmed_swing_resistance": nearest_resistance,
        "resistance_distance_pct": resistance_distance_pct,
        "room_to_obstacle_atr_rebuilt": room_atr,
        "room_to_obstacle_atr_run160": float(row["room_to_obstacle_atr"]) if row.get("room_to_obstacle_atr") else None,
        "entry_guard_allowed_rebuilt": guard_allowed,
        "entry_guard_allowed_run160": str(row.get("entry_guard_allowed", "")).lower() == "true",
        "entry_guard_reason_rebuilt": guard_reason, "signal_atr": atr,
        "score": row.get("score"), "btc_regime": row.get("btc_regime"),
        "exit_reason": row.get("exit_reason"), "net_pct_per_trade": row.get("net_pct"),
        "bars_held": row.get("bars_held"),
    }

def median(values):
    vals = sorted(float(v) for v in values if v is not None)
    if not vals: return None
    n = len(vals)
    return vals[n//2] if n % 2 else (vals[n//2-1] + vals[n//2]) / 2

def main():
    all_trades = download_original_trades()
    trades = [r for r in all_trades if r.get("signal_mode") == "BOTTOM_HUNTER"]
    if len(trades) != 133:
        raise RuntimeError(f"Expected 133 BOTTOM_HUNTER rows, found {len(trades)}")
    if any(r.get("side") != "BUY" for r in trades):
        raise RuntimeError("Unexpected non-BUY BOTTOM_HUNTER trade found")
    output, errors = [], []
    for index, row in enumerate(trades, 1):
        try:
            output.append(reconstruct(row))
            print(f"[{index}/{len(trades)}] OK {row['symbol']} {row['signal_time']}", flush=True)
        except Exception as exc:
            errors.append({"symbol": row.get("symbol"), "signal_time": row.get("signal_time"), "error": str(exc)})
            print(f"[{index}/{len(trades)}] ERROR {row.get('symbol')} {row.get('signal_time')}: {exc}", flush=True)
        time.sleep(0.12)
    if output:
        with (OUT / "bottom_hunter_candle_reconstruction.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(output[0].keys()))
            writer.writeheader()
            writer.writerows(output)
    dists = [r["distance_from_72h_low_pct"] for r in output if r["distance_from_72h_low_pct"] is not None]
    comparable_room = [abs(r["room_to_obstacle_atr_rebuilt"] - r["room_to_obstacle_atr_run160"])
                       for r in output if r["room_to_obstacle_atr_rebuilt"] is not None and r["room_to_obstacle_atr_run160"] is not None]
    range_diffs = [abs(r["range_position_20_rebuilt"] - r["range_position_20_run160"]) for r in output]
    summary = {
        "source_repo": REPO, "source_run_id": 43565343756, "source_artifact_id": RUN160_ARTIFACT_ID,
        "method": "72 closed Binance Spot 1h candles ending at the signal candle close; entry candle excluded",
        "bottom_hunter_rows_expected": len(trades), "rows_reconstructed": len(output), "errors": errors,
        "unique_symbols": len(set(r["symbol"] for r in output)),
        "distance_from_72h_low_pct": {
            "count": len(dists), "median": median(dists),
            "mean": sum(dists) / len(dists) if dists else None,
            "within_4_5pct_count": sum(v <= 4.5 for v in dists),
            "within_4_5pct_pct": 100 * sum(v <= 4.5 for v in dists) / len(dists) if dists else None,
            "within_7pct_count": sum(v <= 7.0 for v in dists),
            "within_7pct_pct": 100 * sum(v <= 7.0 for v in dists) / len(dists) if dists else None,
        },
        "range_position_20_rebuild_max_abs_diff": max(range_diffs, default=None),
        "guard_rebuild_comparable_count": len(comparable_room),
        "guard_rebuild_max_abs_diff_atr": max(comparable_room, default=None),
        "warning": "Diagnostic only, not a strategy change or a new backtest. Binance historical availability can affect retrieval.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    if errors or len(output) != len(trades): sys.exit(1)

if __name__ == "__main__":
    main()
