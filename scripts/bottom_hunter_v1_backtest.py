#!/usr/bin/env python3
"""No-lookahead shared-capital replay for isolated Bottom Hunter v1."""
import csv, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bottom_hunter_v1.core import find_signal, find_early_warning

BASE = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision")
SYMBOLS = [x.strip().upper() for x in os.getenv("BH_BACKTEST_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,TRXUSDT").split(",") if x.strip()]
DAYS = int(os.getenv("BH_BACKTEST_DAYS", "180"))
INITIAL = float(os.getenv("BH_INITIAL_USDT", "1000"))
RISK_FRACTION = float(os.getenv("BH_RISK_FRACTION", "0.01"))
MAX_NOTIONAL = float(os.getenv("BH_MAX_NOTIONAL_USDT", "1000"))
FEE_BPS = float(os.getenv("BH_FEE_BPS", "10"))
SLIP_BPS = float(os.getenv("BH_SLIPPAGE_BPS", "5"))
OUT = Path("bottom-hunter-results")
OUT.mkdir(exist_ok=True)
S = requests.Session()


def fetch(symbol, start_ms, end_ms):
    rows, cursor = [], start_ms
    while cursor < end_ms:
        r = S.get(BASE + "/api/v3/klines", params={"symbol": symbol, "interval": "1h", "startTime": cursor, "endTime": end_ms, "limit": 1000}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + 3600000
        if next_cursor <= cursor:
            raise RuntimeError("Binance pagination did not advance")
        cursor = next_cursor
        if len(batch) < 1000:
            break
        time.sleep(0.08)
    return [{"open_time": int(x[0]), "close_time": int(x[6]), "open": float(x[1]), "high": float(x[2]), "low": float(x[3]), "close": float(x[4]), "volume": float(x[5])} for x in rows if int(x[6]) < end_ms]


def main():
    end = int(datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
    start = end - DAYS * 24 * 3600000
    warm = start - 35 * 24 * 3600000
    series = {}
    for symbol in SYMBOLS:
        bars = fetch(symbol, warm, end)
        if len(bars) < 30:
            raise RuntimeError(f"Insufficient candles for {symbol}: {len(bars)}")
        series[symbol] = bars

    events, warnings = [], []
    for symbol, bars in series.items():
        for i, bar in enumerate(bars):
            if bar["open_time"] < start or bar["close_time"] >= end or i + 1 >= len(bars):
                continue
            history = bars[:i + 1]
            w = find_early_warning(history, symbol)
            if w:
                warnings.append({"symbol": symbol, "signal_time": bar["close_time"], "decline_pct": w["decline_pct"]})
            sig = find_signal(history, symbol)
            if sig:
                events.append({"symbol": symbol, "signal_time": bar["close_time"], "entry_time": bars[i + 1]["open_time"], "entry_bar_index": i + 1, "bars": bars, "signal": sig})
    events.sort(key=lambda e: (e["entry_time"], e["symbol"]))

    equity, peak, max_dd, available_time = INITIAL, INITIAL, 0.0, 0
    trades = []
    for e in events:
        if e["entry_time"] < available_time:
            continue
        bars, sig, idx = e["bars"], e["signal"], e["entry_bar_index"]
        raw_entry = bars[idx]["open"]
        entry = raw_entry * (1 + SLIP_BPS / 10000)
        stop = sig["stop_loss"]  # structural stop from information available at signal close
        risk_per_unit = entry - stop
        if risk_per_unit <= 0:
            continue

        # Critical execution fix: targets must use the actual next-open entry and its risk,
        # not the earlier signal-close price. Report the gap so late/poor fills are visible.
        tp1, tp2 = entry + risk_per_unit * 1.8, entry + risk_per_unit * 2.4
        signal_close = float(sig["signal_close"])
        entry_gap_pct = (entry / signal_close - 1) * 100 if signal_close else 0.0
        qty = min(equity * RISK_FRACTION / risk_per_unit, MAX_NOTIONAL / entry)
        if qty <= 0:
            continue

        remaining, realized, exit_notional = qty, 0.0, 0.0
        exit_time, reason, tp1_done = None, None, False
        highest_high, lowest_low = entry, entry
        for j in range(idx, len(bars)):
            b = bars[j]
            if b["open_time"] >= end:
                break
            highest_high = max(highest_high, b["high"])
            lowest_low = min(lowest_low, b["low"])

            # Conservative OHLC assumption: if stop and target are both touched, stop wins.
            if b["open"] <= stop:
                px = b["open"] * (1 - SLIP_BPS / 10000)
                realized += remaining * (px - entry); exit_notional += remaining * px
                exit_time = b["open_time"]
                reason = "STOP_GAP_AFTER_TP1" if tp1_done else "STOP_GAP"
                break
            if b["low"] <= stop:
                px = stop * (1 - SLIP_BPS / 10000)
                realized += remaining * (px - entry); exit_notional += remaining * px
                exit_time = b["close_time"]
                reason = "STOP_AFTER_TP1" if tp1_done else "STOP"
                break
            if not tp1_done and b["high"] >= tp1 and remaining > 0:
                partial = remaining * 0.5
                px = tp1 * (1 - SLIP_BPS / 10000)
                realized += partial * (px - entry); exit_notional += partial * px
                remaining -= partial
                tp1_done = True
            if b["high"] >= tp2 and remaining > 0:
                px = tp2 * (1 - SLIP_BPS / 10000)
                realized += remaining * (px - entry); exit_notional += remaining * px
                remaining = 0.0
                exit_time, reason = b["close_time"], "TP2_AFTER_TP1"
                break

        if exit_time is None:
            last = next((b for b in reversed(bars[idx:]) if b["open_time"] < end), None)
            if last is None:
                continue
            px = last["close"] * (1 - SLIP_BPS / 10000)
            realized += remaining * (px - entry); exit_notional += remaining * px
            exit_time = last["close_time"]
            reason = "TIME_END_AFTER_TP1" if tp1_done else "TIME_END"

        entry_fee = qty * entry * FEE_BPS / 10000
        fees = entry_fee + exit_notional * FEE_BPS / 10000
        net = realized - fees
        equity += net
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
        available_time = exit_time
        trades.append({
            "symbol": e["symbol"], "signal_time": e["signal_time"], "entry_time": e["entry_time"], "exit_time": exit_time,
            "hold_hours": round(max(0, (exit_time - e["entry_time"]) / 3600000), 3),
            "signal_close": round(signal_close, 10), "entry": round(entry, 10),
            "entry_gap_pct": round(entry_gap_pct, 5), "stop": round(stop, 10),
            "risk_pct_actual": round(risk_per_unit / entry * 100, 5),
            "tp1": round(tp1, 10), "tp2": round(tp2, 10),
            "tp1_hit": tp1_done, "mae_pct": round((lowest_low / entry - 1) * 100, 5),
            "mfe_pct": round((highest_high / entry - 1) * 100, 5),
            "gross_pnl": round(realized, 6), "fees": round(fees, 6), "net_pnl": round(net, 6),
            "equity_after": round(equity, 6), "exit_reason": reason, "fee_bps": FEE_BPS, "slippage_bps": SLIP_BPS
        })

    net = equity - INITIAL
    wins = sum(1 for t in trades if t["net_pnl"] > 0)
    summary = {
        "status": "research_only", "period_days": DAYS,
        "start_utc": datetime.fromtimestamp(start / 1000, timezone.utc).isoformat(),
        "end_utc": datetime.fromtimestamp(end / 1000, timezone.utc).isoformat(),
        "symbols": SYMBOLS, "initial_usdt": INITIAL, "final_usdt": round(equity, 6),
        "net_pnl_usdt": round(net, 6), "return_pct": round(net / INITIAL * 100, 4),
        "max_drawdown_pct": round(max_dd * 100, 4), "trades": len(trades), "wins": wins,
        "win_rate_pct": round(wins / len(trades) * 100, 3) if trades else 0,
        "watch_warnings": len(warnings), "skipped_overlapping_signals": len(events) - len(trades),
        "fee_bps_each_side": FEE_BPS, "slippage_bps_each_side": SLIP_BPS,
        "risk_fraction": RISK_FRACTION, "max_notional_usdt": MAX_NOTIONAL,
        "execution_model": "next-open entry; stop remains structural; TP targets recalculated from actual entry and actual risk",
        "caveats": [
            "Research only; historical replay is not proof of future performance.",
            "Single shared position at a time; conservative stop-first ordering when stop and target are touched in one candle.",
            "TP1 takes half off; stop is not moved to breakeven.",
            "MAE/MFE are candle-extreme estimates and do not resolve intrabar path.",
            "No live orders are placed."
        ]
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    for name, rows in (("trades.csv", trades), ("warnings.csv", warnings)):
        with (OUT / name).open("w", newline="") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
    print(json.dumps(summary, indent=2))
    if not trades:
        raise SystemExit("NO_TRADES: no performance conclusion can be drawn")


if __name__ == "__main__":
    main()
