#!/usr/bin/env python3
"""Paired offline A/B: baseline vs Bottom Hunter-only BUY allowance in full BTC BEARISH.

No live scanner, order execution, Telegram, or production source edits.
The same frozen Binance Spot universe, end time, costs and portfolio settings
are used for both replays. Mixed BTC regimes normalize to NEUTRAL in the experiment.
"""
import json
import os
import sys
from pathlib import Path

# The script lives under scripts/; add repository root so main.py and the
# historical backtest modules resolve consistently on GitHub-hosted runners.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import main

# Freeze one liquid universe before either replay. This avoids A/B universe drift.
max_symbols = int(os.getenv("BTC_EXPERIMENT_MAX_SYMBOLS", "30"))
if not 5 <= max_symbols <= int(getattr(main, "TARGET_MAX_COINS", 100)):
    raise SystemExit("BTC_EXPERIMENT_MAX_SYMBOLS must be between 5 and TARGET_MAX_COINS")

coins = main.get_scan_coins()
symbols = [main.to_binance_usdt_symbol(c) for c in coins]
# Exclude pairs proven by the first replay to lack the required 200 closed warm-up bars.
# These are mostly recently listed, tokenized-equity, or non-directional quote assets.
insufficient_history = {"RLUSDUSDT", "SNDKBUSDT", "UUSDT", "SPCXBUSDT", "HYPEUSDT",
                        "SOXLBUSDT", "RWUSDUSDT", "XAUTUSDT", "NVDABUSDT", "MUBUSDT",
                        "CRCLBUSDT", "MSTRBUSDT"}
symbols = list(dict.fromkeys(s for s in symbols if s and s != "BTCUSDT" and s not in insufficient_history))[:max_symbols]
if len(symbols) < 5:
    raise SystemExit(f"Fail closed: only {len(symbols)} historically warmed symbols were resolved")
if len(symbols) < 5:
    raise SystemExit(f"Fail closed: only {len(symbols)} eligible symbols were resolved")

# Both runs share exactly the same closed-candle end boundary.
end = os.getenv("BACKTEST_END_TIME", "").strip()
if not end:
    end = pd.Timestamp.now(tz="UTC").floor("h").isoformat().replace("+00:00", "Z")
pd.Timestamp(end)  # validate format before starting a long replay
os.environ["BACKTEST_END_TIME"] = end
os.environ["BACKTEST_DAYS"] = os.getenv("BACKTEST_DAYS", "180")
os.environ["BACKTEST_FEE_BPS"] = os.getenv("BACKTEST_FEE_BPS", "10")
os.environ["BACKTEST_SLIPPAGE_BPS"] = os.getenv("BACKTEST_SLIPPAGE_BPS", "5")
os.environ["BACKTEST_INITIAL_CAPITAL_USDT"] = os.getenv("BACKTEST_INITIAL_CAPITAL_USDT", "1000")
os.environ["BACKTEST_RISK_PCT"] = os.getenv("BACKTEST_RISK_PCT", "1.0")
os.environ["BACKTEST_MAX_POSITION_PCT"] = os.getenv("BACKTEST_MAX_POSITION_PCT", "100")
os.environ["BACKTEST_PROFILE_ENGINE"] = "0"
os.environ["BACKTEST_SYMBOLS"] = ",".join(symbols)

import historical_backtest as bt

root = Path("btc-three-state-results")
baseline_dir = root / "baseline"
experiment_dir = root / "bottom-hunter-bearish-only"
baseline_dir.mkdir(parents=True, exist_ok=True)
experiment_dir.mkdir(parents=True, exist_ok=True)
(root / "frozen-universe.json").write_text(json.dumps({
    "symbols": symbols, "count": len(symbols), "selection": "top current Binance Spot USDT directional assets by 24h quote volume, BTC excluded",
    "backtest_end_time": end, "days": int(os.environ["BACKTEST_DAYS"]),
    "fee_bps_per_side": float(os.environ["BACKTEST_FEE_BPS"]),
    "slippage_bps_per_side": float(os.environ["BACKTEST_SLIPPAGE_BPS"]),
    "initial_capital_usdt": float(os.environ["BACKTEST_INITIAL_CAPITAL_USDT"]),
    "risk_pct": float(os.environ["BACKTEST_RISK_PCT"]),
    "max_position_pct": float(os.environ["BACKTEST_MAX_POSITION_PCT"])
}, indent=2), encoding="utf-8")

def run_replay(out_dir):
    bt.OUT = Path(out_dir)
    bt.OUT.mkdir(parents=True, exist_ok=True)
    try:
        bt.run()
    except SystemExit as exc:
        # historical_backtest raises after writing summary when there are no trades.
        if not (bt.OUT / "summary.json").exists():
            raise
        print(f"Replay ended after summary generation: {exc}", flush=True)
    summary_path = bt.OUT / "summary.json"
    if not summary_path.exists():
        raise RuntimeError(f"Missing summary: {summary_path}")
    return json.loads(summary_path.read_text(encoding="utf-8"))

print("=== BASELINE: unchanged production BTC gates ===", flush=True)
baseline = run_replay(baseline_dir)

# Counterfactual: only the Bottom Hunter BUY engine can pass the full BEARISH
# BTC veto. It receives no bullish BTC score bonus. Trend and Breakout keep
# score_btc_regime unchanged and remain blocked in full BEARISH.
original_bottom = main.score_bottom_hunter
original_professional = main.professional_signal_quality_gate
original_analyze = main.analyze_one_symbol
counts = {"mixed_regimes_normalized_to_neutral": 0,
          "bottom_hunter_calls_in_full_bearish_btc": 0,
          "professional_gate_bypasses_for_bottom_hunter": 0}

def experimental_analyze(symbol, btc_regime):
    copied = dict(btc_regime or {})
    combined = str(copied.get("combined", "")).upper()
    if combined in ("MIXED_BEARISH_1H", "MIXED_BULLISH_1H"):
        copied["combined"] = "NEUTRAL"
        counts["mixed_regimes_normalized_to_neutral"] += 1
    return original_analyze(symbol, copied)

def without_bearish_veto(regime):
    copied = dict(regime or {})
    copied["combined"] = ""
    return copied

def experimental_bottom(df_1h, df_30m, btc_regime=None, diagnostic=None, mtf_context=None):
    if str((btc_regime or {}).get("combined", "")).upper() == "BEARISH":
        counts["bottom_hunter_calls_in_full_bearish_btc"] += 1
        return original_bottom(df_1h, df_30m, without_bearish_veto(btc_regime),
                               diagnostic=diagnostic, mtf_context=mtf_context)
    return original_bottom(df_1h, df_30m, btc_regime,
                           diagnostic=diagnostic, mtf_context=mtf_context)

def experimental_professional(signal, data, btc_regime=None):
    mode = str((signal or {}).get("signal_mode", "")).upper()
    if mode == "BOTTOM_HUNTER" and str((btc_regime or {}).get("combined", "")).upper() == "BEARISH":
        counts["professional_gate_bypasses_for_bottom_hunter"] += 1
        return original_professional(signal, data, without_bearish_veto(btc_regime))
    return original_professional(signal, data, btc_regime)

main.analyze_one_symbol = experimental_analyze
main.score_bottom_hunter = experimental_bottom
main.professional_signal_quality_gate = experimental_professional
try:
    print("=== EXPERIMENT: Bottom Hunter only may BUY in full BTC BEARISH ===", flush=True)
    experiment = run_replay(experiment_dir)
finally:
    main.analyze_one_symbol = original_analyze
    main.score_bottom_hunter = original_bottom
    main.professional_signal_quality_gate = original_professional

def engine_metrics(summary, engine="REVERSAL"):
    p = (summary.get("engine_only_portfolio_comparison") or {}).get(engine) or {}
    b = (summary.get("engine_breakdown") or {}).get(engine) or {}
    return {
        "candidate_trades": b.get("candidate_trades"),
        "accepted_trades": p.get("accepted_trades"),
        "rejected_trades": p.get("rejected_trades"),
        "net_pnl_usdt": p.get("net_pnl_usdt"),
        "net_return_pct": p.get("net_return_pct"),
        "max_drawdown_pct": p.get("max_drawdown_pct"),
        "win_rate_pct": p.get("win_rate_pct"),
        "capital_utilization_max_pct": p.get("capital_utilization_max_pct"),
    }

report = {
    "status": "COMPLETED" if baseline.get("status") == "COMPLETED" and experiment.get("status") == "COMPLETED" else "COMPLETED_WITH_ERRORS",
    "policy": "Three states: BULLISH, NEUTRAL (both mixed labels normalize to NEUTRAL), and BEARISH. In full BEARISH, only BOTTOM_HUNTER BUY bypasses the BTC veto and receives no BTC bonus; Trend and Breakout remain blocked. All non-BTC quality gates remain unchanged.",
    "safety": {"live_main_modified": False, "telegram_enabled": False, "orders_enabled": False,
               "production_thresholds_changed": False, "original_functions_restored": True},
    "experiment_counters": counts,
    "universe": symbols,
    "same_window_and_costs": {
        "period_start": baseline.get("period_start"), "period_end": baseline.get("period_end"),
        "days": baseline.get("days"), "fee_slippage": baseline.get("assumptions", {}).get("costs"),
        "capital": baseline.get("assumptions", {}).get("capital")
    },
    "baseline_status": baseline.get("status"), "experiment_status": experiment.get("status"),
    "baseline_errors": len(baseline.get("errors", [])), "experiment_errors": len(experiment.get("errors", [])),
    "bottom_hunter_reversal_ledger_baseline": engine_metrics(baseline),
    "bottom_hunter_reversal_ledger_experiment": engine_metrics(experiment),
    "baseline_summary": "baseline/summary.json", "experiment_summary": "bottom-hunter-bearish-only/summary.json"
}
(root / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2), flush=True)

if baseline.get("status") != "COMPLETED" or experiment.get("status") != "COMPLETED":
    raise SystemExit("Paired A/B incomplete or contains data errors; do not use as decision evidence.")
