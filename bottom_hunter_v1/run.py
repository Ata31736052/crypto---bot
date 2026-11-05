"""Standalone alert-only scanner. It does not place trades."""
import os

from .binance import fetch_closed_klines
from .core import find_signal
from .notify import send_message


def format_signal(s: dict) -> str:
    return (
        f"🟡 BOTTOM HUNTER v1 — {s['symbol']} (BUY)\n"
        f"Timeframe: {s['timeframe']}\n"
        f"Signal close: {s['signal_close']:.8g}\n"
        f"Stop loss: {s['stop_loss']:.8g}\n"
        f"TP1 (1.8R): {s['take_profit_1']:.8g}\n"
        f"TP2 (2.4R): {s['take_profit_2']:.8g}\n"
        f"Risk distance: {s['risk_pct']:.2f}%\n"
        f"Prior decline: {s['decline_pct']:.2f}%\n"
        f"Volume vs median: {s['volume_ratio']:.2f}x\n"
        "Research signal only — not a guaranteed bottom or profit."
    )


def main() -> None:
    symbols = [
        s.strip().upper()
        for s in os.getenv("BH_SYMBOLS", "ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT").split(",")
        if s.strip()
    ]
    interval = os.getenv("BH_INTERVAL", "1h")
    for symbol in symbols:
        try:
            candles = fetch_closed_klines(symbol, interval=interval, limit=100)
            signal = find_signal(candles, symbol)
            if signal:
                send_message(format_signal(signal))
            else:
                print(f"{symbol}: no setup")
        except Exception as exc:
            print(f"{symbol}: scan error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
