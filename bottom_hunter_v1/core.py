"""Small, deterministic Bottom Hunter rule set; no exchange or Telegram side effects."""
from __future__ import annotations

from statistics import median
from typing import Any, Iterable

DEFAULTS = {
    "decline_bars": 6,
    "min_decline_pct": 1.5,
    "volume_lookback": 20,
    "min_volume_ratio": 1.0,
    "atr_period": 14,
    "atr_buffer": 0.10,
    "tp1_r": 1.8,
    "tp2_r": 2.4,
}


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _valid_candle(c: dict[str, Any]) -> bool:
    try:
        o, h, l, close, volume = (float(c[k]) for k in ("open", "high", "low", "close", "volume"))
    except (KeyError, TypeError, ValueError):
        return False
    return (
        all(map(_finite, (o, h, l, close, volume)))
        and min(o, h, l, close) > 0
        and volume >= 0
        and h >= max(o, close, l)
        and l <= min(o, close, h)
    )


def _atr(candles: list[dict[str, Any]], period: int) -> float | None:
    if period < 1 or len(candles) < period + 1:
        return None
    ranges = []
    for i in range(len(candles) - period, len(candles)):
        cur = candles[i]
        prev_close = float(candles[i - 1]["close"])
        ranges.append(max(
            float(cur["high"]) - float(cur["low"]),
            abs(float(cur["high"]) - prev_close),
            abs(float(cur["low"]) - prev_close),
        ))
    value = sum(ranges) / period
    return value if _finite(value) and value > 0 else None


def find_signal(
    candles: Iterable[dict[str, Any]],
    symbol: str,
    *,
    decline_bars: int = DEFAULTS["decline_bars"],
    min_decline_pct: float = DEFAULTS["min_decline_pct"],
    volume_lookback: int = DEFAULTS["volume_lookback"],
    min_volume_ratio: float = DEFAULTS["min_volume_ratio"],
    atr_period: int = DEFAULTS["atr_period"],
    atr_buffer: float = DEFAULTS["atr_buffer"],
    tp1_r: float = DEFAULTS["tp1_r"],
    tp2_r: float = DEFAULTS["tp2_r"],
) -> dict[str, Any] | None:
    """Return a signal from already-closed candles, otherwise None.

    The caller must exclude the currently forming Binance candle.
    All calculations use candles at or before the signal candle; no future bars are read.
    """
    bars = list(candles)
    needed = max(decline_bars + 2, volume_lookback + 1, atr_period + 1)
    if decline_bars < 2 or volume_lookback < 2 or atr_period < 1 or len(bars) < needed:
        return None
    if any(not _valid_candle(c) for c in bars):
        return None

    signal_bar = bars[-1]
    previous_bar = bars[-2]
    decline_start = float(bars[-decline_bars - 1]["close"])
    pre_signal_close = float(bars[-2]["close"])
    if decline_start <= 0:
        return None
    decline_pct = (pre_signal_close / decline_start - 1.0) * 100.0
    if decline_pct > -abs(min_decline_pct):
        return None

    o, close = float(signal_bar["open"]), float(signal_bar["close"])
    if not (close > o and close > float(previous_bar["high"])):
        return None

    reference_volumes = [float(c["volume"]) for c in bars[-volume_lookback - 1:-1]]
    typical_volume = median(reference_volumes)
    if typical_volume <= 0:
        return None
    volume_ratio = float(signal_bar["volume"]) / typical_volume
    if volume_ratio < min_volume_ratio:
        return None

    atr = _atr(bars, atr_period)
    if atr is None:
        return None
    local_low = min(float(c["low"]) for c in bars[-(decline_bars + 1):])
    entry = close
    stop = local_low - atr * max(0.0, atr_buffer)
    risk = entry - stop
    if risk <= 0 or not all(_finite(x) for x in (entry, stop, risk)):
        return None

    return {
        "symbol": symbol.upper(),
        "side": "BUY",
        "timeframe": "1h",
        "signal_close": entry,
        "stop_loss": stop,
        "take_profit_1": entry + risk * tp1_r,
        "take_profit_2": entry + risk * tp2_r,
        "risk_pct": risk / entry * 100.0,
        "decline_pct": decline_pct,
        "volume_ratio": volume_ratio,
        "atr": atr,
        "signal_rule": "decline_then_bullish_close_above_previous_high",
    }
