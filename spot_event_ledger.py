"""Event-driven cash accounting for long-only Spot backtest candidates.

This module is intentionally separate from the legacy ledger until its
integration contract is validated. It never opens shorts and realizes TP1
cash proceeds only for the quantity actually sold.
"""
from pathlib import Path
import pandas as pd


def spot_event_ledger(candidates, out_dir, initial_cash=1000.0, risk_pct=1.0,
                      max_position_pct=100.0):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cash = float(initial_cash)
    accepted, rejected, parsed = [], [], []
    positions = {}
    active_symbols = set()
    realized = {}
    equity_rows = []
    peak = float(initial_cash)
    max_dd = 0.0
    max_util = 0.0

    for idx, source in enumerate(candidates):
        t = dict(source)
        t["_id"] = idx
        t["_entry"] = pd.Timestamp(t["entry_time"])
        t["_events"] = sorted(
            (dict(e) for e in t.get("exit_events", [])),
            key=lambda e: pd.Timestamp(e["time"]),
        )
        if str(t.get("side", "BUY")).upper() != "BUY":
            t["_invalid"] = "SPOT_SELL_CANNOT_OPEN_POSITION"
        elif not t["_events"] or abs(sum(float(e.get("quantity_fraction", 0)) for e in t["_events"]) - 1.0) > 1e-6:
            t["_invalid"] = "INVALID_PARTIAL_EXIT_EVENTS"
        parsed.append(t)

    timeline = sorted(
        {t["_entry"] for t in parsed}
        | {pd.Timestamp(e["time"]) for t in parsed for e in t["_events"]}
        | {pd.Timestamp(p["time"]) for t in parsed for p in t.get("_path", [])}
    )
    entries = {}
    for t in parsed:
        entries.setdefault(t["_entry"], []).append(t)

    event_map = {}
    for t in parsed:
        for n, e in enumerate(t["_events"]):
            event_map.setdefault(pd.Timestamp(e["time"]), []).append((t["_id"], n, e))

    for now in timeline:
        # Mark remaining inventory using closed-candle close marks.
        for p in positions.values():
            for point in p["path"]:
                if pd.Timestamp(point["time"]) == now and float(point["price"]) > 0:
                    p["mark"] = float(point["price"])

        # Realize only the fraction sold at each event (TP1 normally 50%).
        for pid, n, event in event_map.get(now, []):
            p = positions.get(pid)
            if p is None:
                continue
            fraction = float(event["quantity_fraction"])
            if not 0 < fraction <= p["remaining_fraction"] + 1e-9:
                raise AssertionError("Exit fraction exceeds remaining Spot quantity")
            fill = float(event["fill_price"])
            if fill <= 0:
                raise AssertionError("Invalid Spot exit fill")
            proceeds = p["notional"] * fraction * fill / p["entry"]
            fee = p["notional"] * float(event.get("fee_contribution_pct", 0)) / 100.0
            cash += proceeds - fee
            pnl = p["notional"] * fraction * (fill / p["entry"] - 1.0) - fee
            realized[p["symbol"]] = realized.get(p["symbol"], 0.0) + pnl
            p["remaining_fraction"] -= fraction
            p["mark"] = fill
            if p["remaining_fraction"] <= 1e-8:
                active_symbols.discard(p["symbol"])
                del positions[pid]

        for t in sorted(entries.get(now, []),
                        key=lambda x: (-float(x.get("score", 0) or 0), str(x.get("symbol", "")))):
            if t.get("_invalid"):
                t["portfolio_status"] = "REJECTED"
                t["portfolio_reject_reason"] = t["_invalid"]
                rejected.append(t)
                continue
            symbol = str(t.get("symbol", "")).upper()
            if symbol in active_symbols:
                t["portfolio_status"] = "REJECTED"
                t["portfolio_reject_reason"] = "SYMBOL_ALREADY_OPEN"
                rejected.append(t)
                continue
            entry = float(t.get("entry", 0) or 0)
            stop = float(t.get("stop_loss", 0) or 0)
            if entry <= 0 or not 0 < stop < entry:
                t["portfolio_status"] = "REJECTED"
                t["portfolio_reject_reason"] = "INVALID_LONG_SPOT_LEVELS"
                rejected.append(t)
                continue
            equity = cash + sum(p["notional"] * p["remaining_fraction"] * p["mark"] / p["entry"] for p in positions.values())
            risk_fraction = (entry - stop) / entry
            risk_cost = max(0.0, float(t.get("risk_cost_pct", 0) or 0)) / 100.0
            risk_budget = equity * max(0.0, float(risk_pct)) / 100.0
            risk_size = risk_budget / (risk_fraction + risk_cost)
            cap_size = equity * max(0.0, float(max_position_pct)) / 100.0
            entry_fee_pct = max(0.0, float(t.get("fee_cost_pct", 0) or 0) -
                                 sum(float(e.get("fee_contribution_pct", 0)) for e in t["_events"]))
            fee_factor = entry_fee_pct / 100.0
            size = min(risk_size, cap_size, cash / (1.0 + fee_factor))
            if size < 1.0:
                t["portfolio_status"] = "REJECTED"
                t["portfolio_reject_reason"] = "INSUFFICIENT_FREE_CASH"
                rejected.append(t)
                continue
            cash -= size * (1.0 + fee_factor)
            t["portfolio_status"] = "ACCEPTED"
            t["portfolio_reject_reason"] = ""
            t["position_notional_usdt"] = round(size, 6)
            t["risk_budget_usdt"] = round(risk_budget, 6)
            positions[t["_id"]] = {
                "symbol": symbol, "entry": entry, "notional": size,
                "remaining_fraction": 1.0, "mark": entry,
                "path": t.get("_path", []),
            }
            active_symbols.add(symbol)
            accepted.append(t)

        market_value = sum(p["notional"] * p["remaining_fraction"] * p["mark"] / p["entry"] for p in positions.values())
        equity = cash + market_value
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        open_basis = sum(p["notional"] * p["remaining_fraction"] for p in positions.values())
        deployed = cash + open_basis
        util = open_basis / deployed * 100 if deployed > 0 else 0.0
        max_util = max(max_util, util)
        if cash < -1e-6 or util > 100.00001:
            raise AssertionError(f"Spot cash constraint violated at {now}: cash={cash}, utilization={util}")
        equity_rows.append({
            "time": now.isoformat(), "cash_usdt": round(cash, 6),
            "market_value_usdt": round(market_value, 6),
            "open_positions": len(positions), "equity_usdt": round(equity, 6),
            "drawdown_pct": round(dd, 6), "capital_utilization_pct": round(util, 6),
        })

    # No forced liquidation: unresolved positions remain marked, not fictitiously closed.
    final_market_value = sum(p["notional"] * p["remaining_fraction"] * p["mark"] / p["entry"] for p in positions.values())
    final_equity = cash + final_market_value
    for t in parsed:
        if t not in accepted and t not in rejected:
            t["portfolio_status"] = "UNRESOLVED"
    clean = [{k: v for k, v in t.items() if not k.startswith("_")} for t in parsed]
    pd.DataFrame(equity_rows).to_csv(out_dir / "spot_portfolio_equity.csv", index=False)
    pd.DataFrame(clean).to_csv(out_dir / "spot_portfolio_trades.csv", index=False)
    return {
        "accounting_model": "long-only Spot; partial exit proceeds realized by sold quantity; remaining inventory marked to market; no forced closeout",
        "initial_capital_usdt": initial_cash, "final_equity_usdt": round(final_equity, 6),
        "net_pnl_usdt": round(final_equity - initial_cash, 6),
        "net_return_pct": round((final_equity / initial_cash - 1) * 100, 6) if initial_cash else None,
        "max_drawdown_pct": round(max_dd, 6), "candidate_trades": len(parsed),
        "accepted_trades": len(accepted), "rejected_trades": len(rejected),
        "open_positions_at_end": len(positions), "cash_usdt_at_end": round(cash, 6),
        "capital_utilization_max_pct": round(max_util, 6),
        "realized_pnl_by_symbol": {k: round(v, 6) for k, v in sorted(realized.items())},
    }


def spot_event_ledger_self_test(out_dir):
    import tempfile
    t0 = "2026-01-01T01:00:00Z"
    t1 = "2026-01-01T02:00:00Z"
    t2 = "2026-01-01T03:00:00Z"
    base = {
        "symbol": "ETHUSDT", "side": "BUY", "entry_time": t0,
        "entry": 100.0, "stop_loss": 95.0, "score": 95,
        "fee_cost_pct": 0.1, "risk_cost_pct": 0.3,
        "exit_events": [
            {"time": t1, "event": "TP1_PARTIAL", "quantity_fraction": 0.5,
             "fill_price": 109.0, "fee_contribution_pct": 0.0545},
            {"time": t2, "event": "TP2_EXIT", "quantity_fraction": 0.5,
             "fill_price": 112.0, "fee_contribution_pct": 0.056},
        ],
        "_path": [{"time": t1, "price": 109.0}, {"time": t2, "price": 112.0}],
    }
    with tempfile.TemporaryDirectory() as d:
        result = spot_event_ledger([base], d, initial_cash=1000, risk_pct=100, max_position_pct=100)
        # 50% sells at 109, 50% at 112, minus 0.1% entry and event fees.
        size = 1000 / (1 + 0.001)
        expected = size * (0.5 * 1.09 + 0.5 * 1.12) - size * 0.001 - size * (0.0545 + 0.056) / 100
        assert abs(result["final_equity_usdt"] - expected) < 1e-5, (result, expected)
        assert result["open_positions_at_end"] == 0
        assert result["accepted_trades"] == 1
    with tempfile.TemporaryDirectory() as d:
        sell = {**base, "side": "SELL"}
        result = spot_event_ledger([sell], d)
        assert result["accepted_trades"] == 0 and result["rejected_trades"] == 1
    with tempfile.TemporaryDirectory() as d:
        partial = {**base, "exit_events": base["exit_events"][:1],
                   "_path": [{"time": t1, "price": 109.0}]}
        result = spot_event_ledger([partial], d, initial_cash=1000, risk_pct=100, max_position_pct=100)
        assert result["open_positions_at_end"] == 1, "TP1 must not close the remaining half"
        assert result["cash_usdt_at_end"] > 0, "TP1 proceeds must return to available cash"
    print("SPOT_EVENT_LEDGER_SELF_TEST: PASS (long-only, partial proceeds, residual inventory)")
    return True
