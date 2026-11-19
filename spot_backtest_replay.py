"""Offline long-only Spot replay built on the production position lifecycle."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import pandas as pd

from spot_position_manager import (
    build_open_spot_position,
    evaluate_closed_candle,
    apply_exit_transition,
)


def simulate_spot_buy(
    symbol: str,
    signal_time: Any,
    entry_index: int,
    candles: pd.DataFrame,
    signal: Dict[str, Any],
    *,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    max_hold_hours: float = 72.0,
    evaluation_time: Optional[Any] = None,
) -> Tuple[Optional[Dict[str, Any]], int]:
    """Replay one BUY using the live Spot lifecycle; SELL can never open a short.

    Returns a trade with explicit partial exit events and a candle-close mark path.
    Cash/accounting integration is deliberately left to the portfolio ledger.
    """
    if str((signal or {}).get("signal", "")).upper() != "BUY":
        return None, int(entry_index)
    if candles is None or candles.empty or entry_index < 0 or entry_index >= len(candles):
        return None, int(entry_index)

    row = candles.iloc[entry_index]
    raw_entry = float(row["open"])
    if not pd.notna(raw_entry) or raw_entry <= 0:
        return None, int(entry_index)
    slip = max(0.0, float(slippage_bps)) / 10000.0
    entry = raw_entry * (1.0 + slip)

    engine_entry = float(signal.get("entry", 0) or 0)
    engine_stop = float(signal.get("stop_loss", 0) or 0)
    engine_tp1 = float(signal.get("tp1", 0) or 0)
    engine_tp2 = float(signal.get("tp2", 0) or 0)
    if not (0 < engine_stop < engine_entry < engine_tp1 < engine_tp2):
        return None, int(entry_index)

    risk = engine_entry - engine_stop
    tp1_distance = engine_tp1 - engine_entry
    tp2_distance = engine_tp2 - engine_entry
    stop = entry - risk
    tp1 = entry + tp1_distance
    tp2 = entry + tp2_distance

    signal_stamp = pd.Timestamp(signal_time)
    if signal_stamp.tzinfo is None:
        signal_stamp = signal_stamp.tz_localize("UTC")
    else:
        signal_stamp = signal_stamp.tz_convert("UTC")
    entry_stamp = pd.Timestamp(row["open_time"])
    if entry_stamp.tzinfo is None:
        entry_stamp = entry_stamp.tz_localize("UTC")
    else:
        entry_stamp = entry_stamp.tz_convert("UTC")

    position = build_open_spot_position({
        "symbol": symbol,
        "signal": "BUY",
        "entry": entry,
        "stop_loss": stop,
        "tp1": tp1,
        "tp2": tp2,
        "position_quantity": 1.0,
        "candle_time": signal_stamp.isoformat(),
        "score": signal.get("score", 0),
        "engine": signal.get("engine", signal.get("signal_mode", "UNKNOWN")),
    }, opened_at=entry_stamp.isoformat())

    clock = pd.Timestamp.now(tz="UTC") if evaluation_time is None else pd.Timestamp(evaluation_time)
    if clock.tzinfo is None:
        clock = clock.tz_localize("UTC")
    else:
        clock = clock.tz_convert("UTC")

    fee_rate = max(0.0, float(fee_bps)) / 10000.0
    events = []
    path = []
    last_index = int(entry_index)
    entry_fee_pct = fee_rate * 100.0
    total_gross_pct = 0.0
    total_exit_fee_pct = 0.0

    for idx in range(int(entry_index), len(candles)):
        candle = candles.iloc[idx]
        close_time = pd.Timestamp(candle["close_time"])
        if close_time.tzinfo is None:
            close_time = close_time.tz_localize("UTC")
        else:
            close_time = close_time.tz_convert("UTC")
        if close_time > clock:
            break

        candle_payload = {
            "open_time": pd.Timestamp(candle["open_time"]).isoformat(),
            "close_time": close_time.isoformat(),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
        }
        transition = evaluate_closed_candle(
            position, candle_payload, max_hold_hours=max_hold_hours
        )
        path.append({"time": close_time.isoformat(), "price": float(candle["close"])})
        last_index = idx
        event = str(transition.get("event", "NONE")).upper()
        if event != "NONE":
            quantity = float(transition["exit_quantity"])
            raw_exit = float(transition["exit_price"])
            exit_fill = raw_exit * (1.0 - slip)
            fraction = quantity / float(position["initial_quantity"])
            gross_pct = (exit_fill - entry) / entry * 100.0
            exit_fee_pct = fee_rate * 100.0 * fraction * (exit_fill / entry)
            total_gross_pct += gross_pct * fraction
            total_exit_fee_pct += exit_fee_pct
            events.append({
                "time": close_time.isoformat(),
                "event": event,
                "quantity_fraction": fraction,
                "raw_price": raw_exit,
                "fill_price": exit_fill,
                "gross_contribution_pct": gross_pct * fraction,
                "fee_contribution_pct": exit_fee_pct,
            })
            position = apply_exit_transition(position, transition)
            if transition.get("closed"):
                break
        else:
            position = apply_exit_transition(position, transition)

    if not events or position.get("status") != "CLOSED":
        return None, last_index

    entry_slippage_pct = (entry / raw_entry - 1.0) * 100.0
    fee_pct = entry_fee_pct + total_exit_fee_pct
    gross_pct = total_gross_pct
    net_pct = gross_pct - fee_pct
    final_event = events[-1]
    final_time = final_event["time"]
    path[-1] = {"time": final_time, "price": final_event["fill_price"]}

    return {
        "symbol": str(symbol).upper(),
        "side": "BUY",
        "signal_time": signal_stamp.isoformat(),
        "entry_time": entry_stamp.isoformat(),
        "raw_entry": raw_entry,
        "entry": entry,
        "stop_loss": stop,
        "tp1": tp1,
        "tp2": tp2,
        "exit_time": final_time,
        "exit": final_event["fill_price"],
        "exit_reason": final_event["event"],
        "exit_events": events,
        "raw_gross_pct": round(gross_pct + entry_slippage_pct, 6),
        "gross_pct": round(gross_pct, 6),
        "fee_cost_pct": round(fee_pct, 6),
        "slippage_cost_pct": round(entry_slippage_pct + max(0.0, gross_pct - total_gross_pct), 6),
        "cost_pct": round(fee_pct, 6),
        "risk_cost_pct": round(fee_pct + 2.0 * max(0.0, float(slippage_bps)) / 100.0, 6),
        "net_pct": round(net_pct, 6),
        "bars_held": last_index - int(entry_index),
        "score": signal.get("score", 0),
        "strength": signal.get("strength", ""),
        "_path": path,
    }, last_index
