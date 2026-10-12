"""Research-only structural entry/exit gate.

This module is not wired into the live signal engine. It provides a deterministic,
closed-candle testable gate for identifying BUY entries too close to historical
resistance and SELL entries too close to historical support before a strategy
change is considered for production.
"""
from math import isfinite


def _valid_candle(candle):
    try:
        values = [float(candle[k]) for k in ("high", "low", "close")]
    except (KeyError, TypeError, ValueError):
        return False
    high, low, close = values
    return all(isfinite(v) and v > 0 for v in values) and low <= close <= high


def _confirmed_levels(candles, lookback=100, pivot_left=2, pivot_right=2):
    """Find confirmed swing levels from candles strictly before the signal candle.

    The final input candle is the signal candle; it is excluded from levels.
    A pivot is used only when all right-side confirmation candles are already
    closed before the signal, avoiding look-ahead.
    """
    if len(candles) < 2:
        return [], []
    prior = candles[:-1][-lookback:]
    if not all(_valid_candle(c) for c in prior):
        raise ValueError("invalid OHLC in historical candles")
    highs = [float(c["high"]) for c in prior]
    lows = [float(c["low"]) for c in prior]
    resistance, support = [], []
    for i in range(pivot_left, len(prior) - pivot_right):
        high_window = highs[i - pivot_left:i + pivot_right + 1]
        low_window = lows[i - pivot_left:i + pivot_right + 1]
        if highs[i] == max(high_window) and highs[i] > max(high_window[:pivot_left]):
            resistance.append(highs[i])
        if lows[i] == min(low_window) and lows[i] < min(low_window[:pivot_left]):
            support.append(lows[i])
    if not resistance and highs:
        resistance.append(max(highs))
    if not support and lows:
        support.append(min(lows))
    return sorted(set(resistance)), sorted(set(support))


def assess_trade_location(
    candles,
    entry,
    atr,
    side="BUY",
    lookback=100,
    pivot_left=2,
    pivot_right=2,
    min_room_atr=1.5,
    target_buffer_atr=0.25,
    stop_atr=1.5,
    min_rr_tp1=1.8,
    min_rr_tp2=2.4,
    max_stop_pct=13.0,
):
    """Return an auditable location/levels assessment; never emits a signal.

    candles must be ordered old-to-new and include the fully closed signal
    candle as its final row. Entry should be a proposed realistic reference
    price, not the high/low of the signal candle. ATR is from closed data.
    """
    side = str(side or "").upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    entry, atr = float(entry), float(atr)
    if not isfinite(entry) or not isfinite(atr) or entry <= 0 or atr <= 0:
        raise ValueError("entry and ATR must be positive finite numbers")
    if len(candles) < max(3, pivot_left + pivot_right + 2):
        raise ValueError("not enough closed candles for structural levels")
    if min_room_atr <= 0 or target_buffer_atr < 0 or stop_atr <= 0:
        raise ValueError("invalid ATR parameters")

    resistances, supports = _confirmed_levels(candles, lookback, pivot_left, pivot_right)
    if side == "BUY":
        above = [level for level in resistances if level > entry]
        below = [level for level in supports if level < entry]
        resistance = min(above) if above else None
        support = max(below) if below else None
        room = (resistance - entry) / atr if resistance is not None else None
        reasons = []
        if room is not None and room < min_room_atr:
            reasons.append("BUY_TOO_CLOSE_TO_HISTORICAL_RESISTANCE")
        structural_stop = support - target_buffer_atr * atr if support is not None else entry - stop_atr * atr
        stop = min(entry - stop_atr * atr, structural_stop)
        risk = entry - stop
        stop_pct = 100.0 * risk / entry
        if stop_pct > max_stop_pct:
            reasons.append("STRUCTURAL_STOP_TOO_WIDE")
        tp1, tp2 = entry + risk * min_rr_tp1, entry + risk * min_rr_tp2
        if resistance is not None and tp1 >= resistance - target_buffer_atr * atr:
            reasons.append("TP1_BLOCKED_BY_RESISTANCE")
        if resistance is not None and tp2 >= resistance - target_buffer_atr * atr:
            reasons.append("TP2_BLOCKED_BY_RESISTANCE")
        rr1, rr2 = (tp1 - entry) / risk, (tp2 - entry) / risk
    else:
        below = [level for level in supports if level < entry]
        above = [level for level in resistances if level > entry]
        support = max(below) if below else None
        resistance = min(above) if above else None
        room = (entry - support) / atr if support is not None else None
        reasons = []
        if room is not None and room < min_room_atr:
            reasons.append("SELL_TOO_CLOSE_TO_HISTORICAL_SUPPORT")
        structural_stop = resistance + target_buffer_atr * atr if resistance is not None else entry + stop_atr * atr
        stop = max(entry + stop_atr * atr, structural_stop)
        risk = stop - entry
        stop_pct = 100.0 * risk / entry
        if stop_pct > max_stop_pct:
            reasons.append("STRUCTURAL_STOP_TOO_WIDE")
        tp1, tp2 = entry - risk * min_rr_tp1, entry - risk * min_rr_tp2
        if support is not None and tp1 <= support + target_buffer_atr * atr:
            reasons.append("TP1_BLOCKED_BY_SUPPORT")
        if support is not None and tp2 <= support + target_buffer_atr * atr:
            reasons.append("TP2_BLOCKED_BY_SUPPORT")
        rr1, rr2 = (entry - tp1) / risk, (entry - tp2) / risk

    return {
        "accepted": not reasons,
        "side": side,
        "entry": entry,
        "atr": atr,
        "historical_resistance": resistance,
        "historical_support": support,
        "room_to_obstacle_atr": room,
        "stop_loss": stop,
        "tp1": tp1,
        "tp2": tp2,
        "stop_distance_pct": stop_pct,
        "rr_tp1": rr1,
        "rr_tp2": rr2,
        "rejection_reasons": reasons,
        "levels_source": "confirmed_prior_closed_candles_excluding_signal_candle",
    }
