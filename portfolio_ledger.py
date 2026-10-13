"""Shared-cash portfolio accounting for historical signal replay."""
from pathlib import Path
import pandas as pd


def portfolio_ledger(candidates, out_dir, initial_cash=1000.0, risk_pct=1.0,
                     max_position_pct=100.0):
    """Replay candidate trades chronologically on one cash account, no leverage."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cash = float(initial_cash)
    positions = {}
    active_symbols = set()
    accepted, rejected, parsed = [], [], []
    equity_rows = []
    realized_by_symbol = {}
    peak = float(initial_cash)
    max_drawdown = 0.0
    max_utilization = 0.0
    max_gross_exposure_pct_equity = 0.0

    for idx, source in enumerate(candidates):
        trade = dict(source)
        trade["_id"] = idx
        trade["_entry_dt"] = pd.Timestamp(trade["entry_time"])
        trade["_exit_dt"] = pd.Timestamp(trade["exit_time"])
        trade["_path_map"] = {
            pd.Timestamp(point["time"]): float(point["price"])
            for point in trade.get("_path", [])
        }
        parsed.append(trade)

    timeline = sorted(
        {t["_entry_dt"] for t in parsed}
        | {stamp for t in parsed for stamp in t["_path_map"]}
    )
    entries = {}
    for trade in parsed:
        entries.setdefault(trade["_entry_dt"], []).append(trade)

    for now in timeline:
        for position in positions.values():
            price = position["path_map"].get(now)
            if price is not None and price > 0:
                position["mark"] = price

        # Exits are processed before new entries at a timestamp, releasing cash.
        for pid, position in list(positions.items()):
            if position["exit_dt"] <= now:
                pnl = position["notional"] * position["net_pct"] / 100.0
                cash += position["notional"] + pnl
                symbol = position["symbol"]
                realized_by_symbol[symbol] = realized_by_symbol.get(symbol, 0.0) + pnl
                active_symbols.discard(symbol)
                del positions[pid]

        # Deterministic tie-break: higher score first, then symbol name.
        for trade in sorted(entries.get(now, []),
                            key=lambda t: (-float(t.get("score", 0) or 0),
                                           str(t.get("symbol", "")))):
            symbol = str(trade.get("symbol", ""))
            if symbol in active_symbols:
                trade["portfolio_status"] = "REJECTED"
                trade["portfolio_reject_reason"] = "SYMBOL_ALREADY_OPEN"
                rejected.append(trade)
                continue

            equity_before_entry = cash + sum(
                p["notional"] + p["unrealized_pnl"] for p in positions.values()
            )
            if cash <= 0.01 or equity_before_entry <= 0:
                trade["portfolio_status"] = "REJECTED"
                trade["portfolio_reject_reason"] = "INSUFFICIENT_FREE_CASH"
                rejected.append(trade)
                continue

            entry = float(trade.get("entry", 0) or 0)
            stop = float(trade.get("stop_loss", 0) or 0)
            risk_fraction = abs(entry - stop) / entry if entry > 0 and stop > 0 else 0
            if risk_fraction <= 0:
                trade["portfolio_status"] = "REJECTED"
                trade["portfolio_reject_reason"] = "INVALID_STOP_DISTANCE"
                rejected.append(trade)
                continue

            risk_budget = equity_before_entry * max(0.0, float(risk_pct)) / 100.0
            # Include estimated round-trip fees/slippage in risk sizing. Otherwise
            # a stop-out can exceed the configured equity-risk budget by cost_pct.
            # stop distance is a fraction; cost_pct is stored as a percentage.
            cost_pct = max(0.0, float(trade.get("cost_pct", 0) or 0))
            all_in_stop_fraction = risk_fraction + cost_pct / 100.0
            risk_sized_notional = risk_budget / all_in_stop_fraction
            # Reserve enough shared cash to cover configured round-trip costs.
            fee_reserve_factor = 1.0 + cost_pct / 100.0
            cash_limited_notional = cash / fee_reserve_factor
            notional = min(
                risk_sized_notional,
                equity_before_entry * max(0.0, float(max_position_pct)) / 100.0,
                cash_limited_notional,
            )
            if notional < 1.0:
                trade["portfolio_status"] = "REJECTED"
                trade["portfolio_reject_reason"] = "INSUFFICIENT_FREE_CASH"
                rejected.append(trade)
                continue

            trade["portfolio_status"] = "ACCEPTED"
            trade["portfolio_reject_reason"] = ""
            trade["position_notional_usdt"] = round(notional, 6)
            trade["risk_budget_usdt"] = round(risk_budget, 6)
            trade["portfolio_pnl_usdt"] = round(
                notional * float(trade["net_pct"]) / 100.0, 6
            )
            trade["portfolio_return_on_initial_pct"] = round(
                trade["portfolio_pnl_usdt"] / initial_cash * 100, 6
            ) if initial_cash else None

            cash -= notional
            positions[trade["_id"]] = {
                "symbol": symbol,
                "notional": notional,
                "entry": entry,
                "mark": entry,
                "side": str(trade.get("side", "BUY")).upper(),
                "net_pct": float(trade["net_pct"]),
                "cost_pct": float(trade.get("cost_pct", 0) or 0),
                "exit_dt": trade["_exit_dt"],
                "path_map": trade["_path_map"],
                "unrealized_pnl": -notional * float(trade.get("cost_pct", 0) or 0) / 100.0,
            }
            active_symbols.add(symbol)
            accepted.append(trade)

        # Mark open positions using candle closes and round-trip cost estimates.
        for position in positions.values():
            gross_pct = (
                (position["mark"] - position["entry"]) / position["entry"] * 100
                if position["side"] == "BUY"
                else (position["entry"] - position["mark"]) / position["entry"] * 100
            )
            position["unrealized_pnl"] = (
                position["notional"] * (gross_pct - position["cost_pct"]) / 100
            )

        equity = cash + sum(
            p["notional"] + p["unrealized_pnl"] for p in positions.values()
        )
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak * 100 if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        open_notional = sum(p["notional"] for p in positions.values())
        # Cash-backed deployment uses unmarked cost basis plus remaining cash.
        # Dividing cost basis by marked-to-market equity can exceed 100% during
        # an unrealized loss; that is drawdown, not cash overspending.
        deployed_capital = cash + open_notional
        utilization = open_notional / deployed_capital * 100 if deployed_capital > 0 else 0.0
        gross_exposure_pct_equity = open_notional / equity * 100 if equity > 0 else 0.0
        max_utilization = max(max_utilization, utilization)
        max_gross_exposure_pct_equity = max(max_gross_exposure_pct_equity, gross_exposure_pct_equity)
        if cash < -1e-6:
            raise AssertionError(f"Shared-cash ledger overspent at {now}: cash={cash:.8f}")
        if utilization > 100.0 + 1e-5:
            raise AssertionError(f"Cash-backed utilization exceeded 100% at {now}: {utilization:.6f}%")
        equity_rows.append({
            "time": now.isoformat(),
            "cash_usdt": round(cash, 6),
            "open_positions": len(positions),
            "open_notional_usdt": round(open_notional, 6),
            "equity_usdt": round(equity, 6),
            "drawdown_pct": round(drawdown, 6),
            "capital_utilization_pct": round(utilization, 6),
            "gross_exposure_pct_equity": round(gross_exposure_pct_equity, 6),
        })

    # Defensive close-out for any candidate path that did not include its exit timestamp.
    for position in positions.values():
        pnl = position["notional"] * position["net_pct"] / 100.0
        cash += position["notional"] + pnl
        symbol = position["symbol"]
        realized_by_symbol[symbol] = realized_by_symbol.get(symbol, 0.0) + pnl

    final_equity = cash
    status_by_id = {t["_id"]: t for t in accepted + rejected}
    for trade in parsed:
        status = status_by_id.get(trade["_id"])
        if status:
            trade["portfolio_status"] = status.get("portfolio_status", "REJECTED")
            trade["portfolio_reject_reason"] = status.get("portfolio_reject_reason", "")
            for key in ("position_notional_usdt", "risk_budget_usdt",
                        "portfolio_pnl_usdt", "portfolio_return_on_initial_pct"):
                if key in status:
                    trade[key] = status[key]

    symbols = sorted({str(t.get("symbol", "")) for t in parsed})
    per_symbol = []
    for symbol in symbols:
        trades = [t for t in accepted if str(t.get("symbol", "")) == symbol]
        per_symbol.append({
            "symbol": symbol,
            "candidate_trades": sum(str(t.get("symbol", "")) == symbol for t in parsed),
            "accepted_trades": len(trades),
            "rejected_trades": sum(str(t.get("symbol", "")) == symbol for t in rejected),
            "realized_pnl_usdt": round(realized_by_symbol.get(symbol, 0.0), 6),
            "win_rate_pct": round(
                sum(float(t.get("net_pct", 0)) > 0 for t in trades) / len(trades) * 100, 3
            ) if trades else None,
        })

    pd.DataFrame(equity_rows).to_csv(out_dir / "portfolio_equity.csv", index=False)
    pd.DataFrame(per_symbol).to_csv(out_dir / "per_symbol.csv", index=False)
    pd.DataFrame([{k: v for k, v in t.items() if not k.startswith("_")}
                  for t in parsed]).to_csv(out_dir / "portfolio_trades.csv", index=False)

    return {
        "initial_capital_usdt": initial_cash,
        "final_equity_usdt": round(final_equity, 6),
        "net_pnl_usdt": round(final_equity - initial_cash, 6),
        "net_return_pct": round((final_equity / initial_cash - 1) * 100, 6) if initial_cash else None,
        "max_drawdown_pct": round(max_drawdown, 6),
        "candidate_trades": len(parsed),
        "accepted_trades": len(accepted),
        "rejected_trades": len(rejected),
        "capital_utilization_max_pct": round(max_utilization, 6),
        "gross_exposure_max_pct_equity": round(max_gross_exposure_pct_equity, 6),
        "risk_per_trade_pct_of_equity": risk_pct,
        "max_position_pct_of_equity": max_position_pct,
        "execution_model": "one shared cash account; no leverage; position size is min(1% equity risk / stop distance, position cap, free cash); open positions marked to market at historical hourly closes; fees/slippage included",
        "per_symbol": per_symbol,
    }


def portfolio_ledger_self_test(out_dir):
    """Deterministic checks for shared capital, release, fees, and mark-to-market drawdown."""
    import tempfile

    def make_trade(symbol, entry_time, exit_time, net_pct, score=95,
                   cost_pct=0.0, exit_price=None):
        entry = 100.0
        if exit_price is None:
            exit_price = entry * (1.0 + net_pct / 100.0)
        return {
            "symbol": symbol, "side": "BUY", "entry_time": entry_time,
            "exit_time": exit_time, "entry": entry, "stop_loss": 95.0,
            "net_pct": net_pct, "cost_pct": cost_pct, "score": score,
            "_path": [{"time": exit_time, "price": exit_price}],
        }

    t0 = "2026-01-01T00:00:00+00:00"
    t1 = "2026-01-01T01:00:00+00:00"
    t2 = "2026-01-01T02:00:00+00:00"
    t3 = "2026-01-01T03:00:00+00:00"
    t4 = "2026-01-01T04:00:00+00:00"

    # 1) Simultaneous signals use deterministic score priority and cannot overspend cash.
    with tempfile.TemporaryDirectory() as d:
        simultaneous = [
            make_trade("AAAUSDT", t0, t2, 0.0, score=99),
            make_trade("BBBUSDT", t0, t2, 0.0, score=95),
            make_trade("CCCUSDT", t0, t2, 0.0, score=94),
        ]
        r = portfolio_ledger(simultaneous, d, initial_cash=1000, risk_pct=100,
                             max_position_pct=100)
        assert r["accepted_trades"] == 1, "full-cash simultaneous trades must not overlap allocations"
        assert r["rejected_trades"] == 2
        assert r["capital_utilization_max_pct"] <= 100.0 + 1e-5, "fee reserve must keep utilization within account equity"
        rows = pd.read_csv(Path(d) / "portfolio_trades.csv")
        accepted_symbols = rows.loc[rows["portfolio_status"] == "ACCEPTED", "symbol"].tolist()
        assert accepted_symbols == ["AAAUSDT"], "higher-score candidate must win timestamp tie"

    # 2) Cash reserved by an open position is released after its exit.
    with tempfile.TemporaryDirectory() as d:
        sequential = [
            make_trade("AAAUSDT", t0, t2, 0.0),
            make_trade("BBBUSDT", t3, t4, 0.0),
        ]
        r = portfolio_ledger(sequential, d, initial_cash=1000, risk_pct=100,
                             max_position_pct=100)
        assert r["accepted_trades"] == 2, "capital must become reusable after exit"
        assert r["rejected_trades"] == 0
        assert abs(r["final_equity_usdt"] - 1000.0) < 1e-6

    # 3) Net PnL and fees scale with the notional actually allocated, not the candidate's
    #    theoretical full-account size.
    with tempfile.TemporaryDirectory() as d_full, tempfile.TemporaryDirectory() as d_half:
        candidate = [make_trade("AAAUSDT", t0, t2, 0.7, cost_pct=0.3, exit_price=101.0)]
        full = portfolio_ledger(candidate, d_full, initial_cash=1000, risk_pct=100,
                                max_position_pct=100)
        half = portfolio_ledger(candidate, d_half, initial_cash=1000, risk_pct=100,
                                max_position_pct=50)
        assert full["capital_utilization_max_pct"] <= 100.0 + 1e-5, "fees must not cause >100% utilization"
        assert full["net_pnl_usdt"] < 7.0, "reserved fees must reduce allocated notional"
        assert abs(half["net_pnl_usdt"] - 3.5) < 1e-5
        assert abs(full["net_pnl_usdt"] / half["net_pnl_usdt"] - 1.994) < 0.01

    # 4) The all-in stop loss, including fees/slippage, must stay within risk budget.
    with tempfile.TemporaryDirectory() as d:
        stop_trade = make_trade("AAAUSDT", t0, t2, -2.3, cost_pct=0.3, exit_price=98.0)
        stop_trade["stop_loss"] = 98.0
        r = portfolio_ledger([stop_trade], d, initial_cash=1000, risk_pct=1,
                             max_position_pct=100)
        row = pd.read_csv(Path(d) / "portfolio_trades.csv").iloc[0]
        all_in_loss = -float(row["portfolio_pnl_usdt"])
        assert abs(all_in_loss - 10.0) < 1e-4, (
            f"all-in stop loss {all_in_loss} must equal $10 risk budget"
        )
        assert float(row["position_notional_usdt"]) < 500.0, (
            "fees/slippage must be included in stop-distance position sizing"
        )

    # 5) Equity is marked to market and drawdown is measured from the running peak.
    with tempfile.TemporaryDirectory() as d:
        losing = [make_trade("AAAUSDT", t0, t2, -5.3, cost_pct=0.3, exit_price=95.0)]
        # Include a pre-exit mark so the equity curve captures the open loss.
        losing[0]["_path"] = [
            {"time": t1, "price": 95.0},
            {"time": t2, "price": 95.0},
        ]
        r = portfolio_ledger(losing, d, initial_cash=1000, risk_pct=100,
                             max_position_pct=100)
        expected_notional = 1000.0 / 1.003
        expected_equity = 1000.0 - expected_notional * 0.053
        expected_drawdown = (1000.0 - expected_equity) / 1000.0 * 100.0
        assert abs(r["final_equity_usdt"] - expected_equity) < 1e-5
        assert abs(r["max_drawdown_pct"] - expected_drawdown) < 1e-4
        assert r["capital_utilization_max_pct"] <= 100.0 + 1e-5
        assert r["gross_exposure_max_pct_equity"] > 100.0, (
            "gross exposure may exceed marked-to-market equity during unrealized losses; "
            "keep this distinct from cash-backed utilization"
        )
        curve = pd.read_csv(Path(d) / "portfolio_equity.csv")
        assert curve["equity_usdt"].min() <= expected_equity + 1e-5
        assert curve["drawdown_pct"].max() >= expected_drawdown - 1e-4

    print("PORTFOLIO_LEDGER_SELF_TEST: PASS (simultaneous allocation, capital release, fee scaling, drawdown)")
