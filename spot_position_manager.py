"""Stateful, long-only Binance Spot position lifecycle helpers.

This module is deliberately pure: it does not call Binance, Telegram, or place
orders. The caller persists returned position state and sends human-readable
alerts. OHLC ambiguity is resolved conservatively.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _number(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_open_spot_position(signal: Dict[str, Any], opened_at: Optional[str] = None) -> Dict[str, Any]:
    """Create a trackable long Spot position only from a fully risk-sized BUY."""
    if not isinstance(signal, dict) or str(signal.get("signal", "")).upper() != "BUY":
        raise ValueError("Only BUY signals can open a Spot position")
    symbol = str(signal.get("symbol", "")).upper().strip()
    entry = _number(signal.get("entry"))
    stop = _number(signal.get("stop_loss"))
    tp1 = _number(signal.get("tp1"))
    tp2 = _number(signal.get("tp2"))
    quantity = _number(signal.get("position_quantity"))
    if not symbol or any(x is None or x <= 0 for x in (entry, stop, tp1, tp2, quantity)):
        raise ValueError("BUY signal is missing valid symbol, levels, or position quantity")
    if not stop < entry < tp1 < tp2:
        raise ValueError("Spot BUY levels must satisfy stop_loss < entry < tp1 < tp2")
    stamp = opened_at or datetime.now(timezone.utc).isoformat()
    candle_time = str(signal.get("candle_time") or "")
    return {
        "symbol": symbol,
        "side": "BUY",
        "status": "OPEN",
        "entry": entry,
        "stop_loss": stop,
        "initial_stop_loss": stop,
        "tp1": tp1,
        "tp2": tp2,
        "initial_quantity": quantity,
        "remaining_quantity": quantity,
        "tp1_done": False,
        "opened_at": stamp,
        "entry_candle_time": candle_time,
        # Do not evaluate the already-closed candle that created this signal.
        "last_checked_candle": candle_time,
        "signal_key": str(signal.get("signal_key") or ""),
        "entry_score": int(_number(signal.get("score")) or 0),
        "entry_engine": str(signal.get("engine") or signal.get("signal_mode") or "TREND"),
    }


def evaluate_closed_candle(
    position: Dict[str, Any],
    candle: Dict[str, Any],
    *,
    trend_invalidated: bool = False,
    max_hold_hours: float = 72.0,
) -> Dict[str, Any]:
    """Return one conservative exit transition for a fully closed 1H candle.

    If both the active stop and an upside target are touched in one candle,
    assume the stop was hit first. After TP1, the stop is moved to breakeven.
    TP2 is evaluated from a later candle so a single OHLC bar cannot imply an
    unknowable intrabar sequence.
    """
    if not isinstance(position, dict) or str(position.get("status", "")).upper() != "OPEN":
        return {"event": "NONE", "reason": "POSITION_NOT_OPEN"}
    if not isinstance(candle, dict):
        return {"event": "NONE", "reason": "INVALID_CANDLE"}

    high = _number(candle.get("high"))
    low = _number(candle.get("low"))
    close = _number(candle.get("close"))
    entry = _number(position.get("entry"))
    stop = _number(position.get("stop_loss"))
    tp1 = _number(position.get("tp1"))
    tp2 = _number(position.get("tp2"))
    remaining = _number(position.get("remaining_quantity"))
    if any(x is None or x <= 0 for x in (high, low, close, entry, stop, tp1, tp2, remaining)):
        return {"event": "NONE", "reason": "INVALID_POSITION_OR_CANDLE"}
    if low > high:
        return {"event": "NONE", "reason": "INVALID_OHLC_RANGE"}

    candle_time = str(candle.get("open_time") or candle.get("time") or "")
    last_checked = str(position.get("last_checked_candle") or "")
    if candle_time and last_checked and candle_time <= last_checked:
        return {"event": "NONE", "reason": "CANDLE_ALREADY_PROCESSED"}

    tp1_done = bool(position.get("tp1_done"))
    held_from = _timestamp(position.get("opened_at"))
    candle_dt = _timestamp(candle.get("close_time") or candle.get("time") or candle_time)
    age_hours = ((candle_dt - held_from).total_seconds() / 3600.0) if held_from and candle_dt else 0.0

    def result(event: str, reason: str, price: float, quantity: float, *, remaining_after: float, stop_after: float, closed: bool):
        return {
            "event": event,
            "reason": reason,
            "exit_price": float(price),
            "exit_quantity": float(quantity),
            "remaining_quantity": float(remaining_after),
            "stop_loss_after": float(stop_after),
            "tp1_done_after": bool(tp1_done or event == "TP1_PARTIAL"),
            "closed": bool(closed),
            "candle_time": candle_time,
        }

    # Stop-first ordering protects against optimistic OHLC assumptions.
    if low <= stop:
        event = "BREAK_EVEN_EXIT" if tp1_done and stop >= entry else "STOP_LOSS"
        return result(event, "PROTECTIVE_STOP_TOUCHED", stop, remaining,
                      remaining_after=0.0, stop_after=stop, closed=True)

    if not tp1_done and high >= tp1:
        partial = min(remaining, _number(position.get("initial_quantity")) * 0.5)
        rest = max(0.0, remaining - partial)
        return result("TP1_PARTIAL", "FIRST_TARGET_TOUCHED", tp1, partial,
                      remaining_after=rest, stop_after=entry, closed=(rest <= 1e-12))

    if tp1_done and high >= tp2:
        return result("TP2_EXIT", "SECOND_TARGET_TOUCHED", tp2, remaining,
                      remaining_after=0.0, stop_after=stop, closed=True)

    if trend_invalidated:
        return result("TREND_INVALIDATION_EXIT", "CLOSED_1H_TREND_INVALIDATION", close, remaining,
                      remaining_after=0.0, stop_after=stop, closed=True)

    if max_hold_hours > 0 and age_hours >= max_hold_hours:
        return result("TIME_EXIT", "MAX_HOLD_TIME_REACHED", close, remaining,
                      remaining_after=0.0, stop_after=stop, closed=True)

    return {"event": "NONE", "reason": "NO_EXIT_CONDITION", "candle_time": candle_time}


def apply_exit_transition(position: Dict[str, Any], transition: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a successful-notification transition to a copy of the position."""
    updated = dict(position)
    event = str(transition.get("event", "NONE")).upper()
    if event == "NONE":
        if transition.get("candle_time"):
            updated["last_checked_candle"] = transition["candle_time"]
        return updated
    updated["remaining_quantity"] = float(transition.get("remaining_quantity", 0.0))
    updated["stop_loss"] = float(transition.get("stop_loss_after", updated.get("stop_loss", 0.0)))
    updated["tp1_done"] = bool(transition.get("tp1_done_after", updated.get("tp1_done", False)))
    if transition.get("candle_time"):
        updated["last_checked_candle"] = transition["candle_time"]
    updated["last_exit_event"] = event
    if transition.get("closed"):
        updated["status"] = "CLOSED"
        updated["closed_at_candle"] = transition.get("candle_time", "")
    return updated


def spot_exit_self_test() -> bool:
    """Deterministic safety tests for long-only Spot exit transitions."""
    buy = {
        "symbol": "ETHUSDT", "signal": "BUY", "score": 95,
        "entry": 100.0, "stop_loss": 95.0, "tp1": 109.0, "tp2": 112.0,
        "position_quantity": 2.0, "candle_time": "2026-01-01T00:00:00+00:00",
    }
    p = build_open_spot_position(buy, "2026-01-01T01:00:00+00:00")
    assert p["remaining_quantity"] == 2.0 and p["status"] == "OPEN"
    try:
        build_open_spot_position({**buy, "signal": "SELL"})
    except ValueError:
        pass
    else:
        raise AssertionError("SELL must never open a Spot short position")

    # Same candle touches stop and TP1: conservatively take the stop.
    stop_first = evaluate_closed_candle(p, {
        "open_time": "2026-01-01T01:00:00+00:00", "high": 110.0,
        "low": 94.0, "close": 108.0,
    })
    assert stop_first["event"] == "STOP_LOSS" and stop_first["closed"]

    # TP1 exits half, then moves the remaining stop to entry.
    tp1 = evaluate_closed_candle(p, {
        "open_time": "2026-01-01T01:00:00+00:00", "high": 110.0,
        "low": 99.0, "close": 109.5,
    })
    assert tp1["event"] == "TP1_PARTIAL"
    assert tp1["exit_quantity"] == 1.0 and tp1["remaining_quantity"] == 1.0
    assert tp1["stop_loss_after"] == 100.0 and tp1["tp1_done_after"]
    p = apply_exit_transition(p, tp1)
    assert p["tp1_done"] and p["stop_loss"] == 100.0 and p["status"] == "OPEN"

    # The breakeven stop wins over TP2 when both are touched in the same bar.
    ambiguous = evaluate_closed_candle(p, {
        "open_time": "2026-01-01T02:00:00+00:00", "high": 113.0,
        "low": 99.0, "close": 111.0,
    })
    assert ambiguous["event"] == "BREAK_EVEN_EXIT" and ambiguous["closed"]

    p = apply_exit_transition(p, tp1)
    tp2 = evaluate_closed_candle(p, {
        "open_time": "2026-01-01T02:00:00+00:00", "high": 113.0,
        "low": 101.0, "close": 112.5,
    })
    assert tp2["event"] == "TP2_EXIT" and tp2["closed"]

    invalidation = evaluate_closed_candle(
        build_open_spot_position(buy, "2026-01-01T01:00:00+00:00"),
        {"open_time": "2026-01-01T01:00:00+00:00", "high": 105.0, "low": 101.0, "close": 102.0},
        trend_invalidated=True,
    )
    assert invalidation["event"] == "TREND_INVALIDATION_EXIT"

    duplicate = evaluate_closed_candle(p, {
        "open_time": "2026-01-01T02:00:00+00:00", "high": 113.0,
        "low": 101.0, "close": 112.5,
    })
    assert duplicate["event"] == "NONE" and duplicate["reason"] == "CANDLE_ALREADY_PROCESSED"
    return True
