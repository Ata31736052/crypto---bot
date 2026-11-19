#!/usr/bin/env python3
"""Offline paired 180-day A/B: test RSI ceilings for Bottom Hunter only.

This is research-only. It does not edit production thresholds, enable Telegram,
place orders, or alter Trend/Breakout/SELL logic. All runs use the same frozen
28-symbol universe, end boundary, costs, capital and portfolio execution model.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import main
import historical_backtest as bt

SYMBOLS = [
    "ETHUSDT", "ZECUSDT", "XRPUSDT", "SOLUSDT", "ONEUSDT", "BNBUSDT",
    "NEARUSDT", "PEPEUSDT", "UNIUSDT", "TRXUSDT", "SUIUSDT", "PUMPUSDT",
    "ENAUSDT", "DOGEUSDT", "QNTUSDT", "WLDUSDT", "INJUSDT", "LINKUSDT",
    "TRUMPUSDT", "AAVEUSDT", "LTCUSDT", "CYBERUSDT", "ACTUSDT", "ADAUSDT",
    "PAXGUSDT", "CELOUSDT", "GTCUSDT", "AVAXUSDT"
]
assert len(SYMBOLS) == 28 and "BTCUSDT" not in SYMBOLS

end = os.getenv("BACKTEST_END_TIME", "2026-11-07T17:00:00Z").strip()
pd.Timestamp(end)
os.environ.update({
    "BACKTEST_END_TIME": end,
    "BACKTEST_DAYS": os.getenv("BACKTEST_DAYS", "180"),
    "BACKTEST_FEE_BPS": os.getenv("BACKTEST_FEE_BPS", "10"),
    "BACKTEST_SLIPPAGE_BPS": os.getenv("BACKTEST_SLIPPAGE_BPS", "5"),
    "BACKTEST_INITIAL_CAPITAL_USDT": os.getenv("BACKTEST_INITIAL_CAPITAL_USDT", "1000"),
    "BACKTEST_RISK_PCT": os.getenv("BACKTEST_RISK_PCT", "1.0"),
    "BACKTEST_MAX_POSITION_PCT": os.getenv("BACKTEST_MAX_POSITION_PCT", "100"),
    "BACKTEST_PROFILE_ENGINE": "0",
    "BACKTEST_SYMBOLS": ",".join(SYMBOLS),
})

ROOT = Path("btc-bottom-hunter-rsi-ab")
ROOT.mkdir(parents=True, exist_ok=True)
original = main.score_bottom_hunter

def run_one(label, ceiling=None):
    out = ROOT / label
    out.mkdir(parents=True, exist_ok=True)
    bt.OUT = out
    blocked = {"high_rsi_bottom_hunter_candidates": 0}
    if ceiling is None:
        main.score_bottom_hunter = original
    else:
        def capped(*args, **kwargs):
            candidate = original(*args, **kwargs)
            if candidate and float(candidate.get("rsi", 0) or 0) > ceiling:
                blocked["high_rsi_bottom_hunter_candidates"] += 1
                return None
            return candidate
        main.score_bottom_hunter = capped
    try:
        print(f"=== {label}: RSI ceiling={ceiling} ===", flush=True)
        try:
            bt.run()
        except SystemExit as exc:
            if not (out / "summary.json").exists():
                raise
            print(f"Replay stopped after summary generation: {exc}", flush=True)
        path = out / "summary.json"
        if not path.exists():
            raise RuntimeError(f"Missing summary file: {path}")
        summary = json.loads(path.read_text(encoding="utf-8"))
        rev = (summary.get("engine_only_portfolio_comparison") or {}).get("REVERSAL") or {}
        return {
            "label": label,
            "rsi_ceiling": ceiling,
            "status": summary.get("status"),
            "errors": len(summary.get("errors", [])),
            "period_start": summary.get("period_start"),
            "period_end": summary.get("period_end"),
            "days": summary.get("days"),
            "candidate_trades": rev.get("candidate_trades"),
            "accepted_trades": rev.get("accepted_trades"),
            "rejected_trades": rev.get("rejected_trades"),
            "net_pnl_usdt": rev.get("net_pnl_usdt"),
            "net_return_pct": rev.get("net_return_pct"),
            "max_drawdown_pct": rev.get("max_drawdown_pct"),
            "capital_utilization_max_pct": rev.get("capital_utilization_max_pct"),
            **blocked,
            "summary_path": str(path),
        }
    finally:
        main.score_bottom_hunter = original

results = []
try:
    results.append(run_one("baseline_no_rsi_ceiling", None))
    for ceiling in (50, 55, 60):
        results.append(run_one(f"rsi_max_{ceiling}", ceiling))
finally:
    main.score_bottom_hunter = original

valid = [x for x in results if x["status"] == "COMPLETED" and x["errors"] == 0]
report = {
    "status": "COMPLETED" if len(valid) == len(results) else "COMPLETED_WITH_ERRORS",
    "purpose": "Measure whether excluding late/high-RSI Bottom Hunter entries improves net portfolio outcomes without changing any production setting.",
    "safety": {
        "production_source_modified": False,
        "production_thresholds_changed": False,
        "telegram_enabled": False,
        "orders_enabled": False,
        "trend_breakout_sell_logic_modified": False,
        "original_function_restored": True
    },
    "frozen_universe": SYMBOLS,
    "assumptions": {
        "end": end,
        "days": int(os.environ["BACKTEST_DAYS"]),
        "fee_bps_per_side": float(os.environ["BACKTEST_FEE_BPS"]),
        "slippage_bps_per_side": float(os.environ["BACKTEST_SLIPPAGE_BPS"]),
        "initial_capital_usdt": float(os.environ["BACKTEST_INITIAL_CAPITAL_USDT"]),
        "risk_pct": float(os.environ["BACKTEST_RISK_PCT"]),
        "max_position_pct": float(os.environ["BACKTEST_MAX_POSITION_PCT"])
    },
    "results": results
}
(ROOT / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)
if report["status"] != "COMPLETED":
    raise SystemExit("One or more paired replays incomplete; do not use as decision evidence.")
