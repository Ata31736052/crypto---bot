#!/usr/bin/env python3
"""Offline cap=3 vs cap=5 vs uncapped replay for Run #160 REVERSAL candidates.

Reconstructs hourly quote-volume ranking and hourly mark-to-market paths from
Binance Spot klines. Fails closed if source data are missing or the uncapped
portfolio cannot reproduce the published Run #160 baseline.
"""
from __future__ import annotations
import argparse, json, math, time, zipfile
from pathlib import Path
from datetime import timedelta

import pandas as pd
import requests
from run160_portfolio_ledger import portfolio_ledger

REPO = "Ata31736052/crypto---bot"
RUN_ID = 43565343756
ARTIFACT_ID = 14102983195
BASE = "https://data-api.binance.vision"
INTERVAL_MS = 3_600_000
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ApexSignal-offline-cap-diagnostic/1.0"})

def utc_ms(value) -> int:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp() * 1000)

def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    cursor = start_ms
    all_rows = []
    while cursor < end_ms:
        params = {"symbol": symbol, "interval": "1h", "startTime": cursor,
                  "endTime": end_ms, "limit": 1000}
        last_error = None
        batch = None
        for attempt in range(6):
            try:
                response = SESSION.get(f"{BASE}/api/v3/klines", params=params, timeout=30)
                if response.status_code in (418, 429):
                    time.sleep(min(30, 2 ** attempt))
                    continue
                response.raise_for_status()
                batch = response.json()
                if not isinstance(batch, list):
                    raise RuntimeError(f"{symbol}: invalid Binance hourly-candle response")
                break
            except Exception as exc:
                last_error = exc
                time.sleep(0.5 * (attempt + 1))
        if batch is None:
            raise RuntimeError(f"Unable to fetch {symbol} after retries: {last_error}")
        if not batch:
            break
        all_rows.extend(batch)
        next_cursor = int(batch[-1][0]) + INTERVAL_MS
        if next_cursor <= cursor:
            raise RuntimeError(f"{symbol}: Binance pagination stalled at {cursor}")
        cursor = next_cursor
        if len(batch) < 1000:
            break
        time.sleep(0.12)
    if not all_rows:
        raise RuntimeError(f"{symbol}: Binance returned no hourly candles in requested window")
    frame = pd.DataFrame(all_rows, columns=[
        "open_ms","open","high","low","close","base_volume","close_ms",
        "quote_volume","trades","taker_base","taker_quote","ignore"
    ])
    for col in ("open","high","low","close","quote_volume"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    frame["open_ms"] = pd.to_numeric(frame["open_ms"], errors="raise").astype("int64")
    frame["close_ms"] = pd.to_numeric(frame["close_ms"], errors="raise").astype("int64")
    frame = frame[(frame.open_ms >= start_ms) & (frame.open_ms < end_ms)].copy()
    return frame.sort_values("open_ms").drop_duplicates("open_ms")

def load_inputs(artifact_zip: Path):
    with zipfile.ZipFile(artifact_zip) as zf:
        summary = json.loads(zf.read("summary.json"))
        trades = pd.read_csv(zf.open("engine-comparison/reversal/portfolio_trades.csv"))
    required = {"symbols","engine_only_portfolio_comparison"}
    if not required.issubset(summary):
        raise RuntimeError("Run #160 summary schema is incomplete")
    if len(trades) != 135 or not (trades["engine"].astype(str).str.upper() == "REVERSAL").all():
        raise RuntimeError("Unexpected Run #160 REVERSAL candidate set; expected 135 REVERSAL rows")
    return summary, trades

def make_path(trade, bars: pd.DataFrame):
    entry_ms, exit_ms = utc_ms(trade["entry_time"]), utc_ms(trade["exit_time"])
    path_bars = bars[(bars.open_ms >= entry_ms) & (bars.close_ms <= exit_ms)].sort_values("open_ms")
    expected = int((exit_ms - (entry_ms + INTERVAL_MS - 1)) // INTERVAL_MS) + 1
    if path_bars.empty or int(path_bars.iloc[0].open_ms) != entry_ms:
        raise RuntimeError(f"{trade['symbol']}: missing entry candle for {trade['entry_time']}")
    # The historical engine marks each completed hourly candle at close, and
    # uses its adverse/slipped exit fill on the final candle.
    path = []
    for row in path_bars.itertuples():
        price = float(trade["exit"]) if int(row.close_ms) == exit_ms else float(row.close)
        path.append({"time": pd.to_datetime(int(row.close_ms), unit="ms", utc=True).isoformat(),
                     "price": price})
    if not path or int(pd.Timestamp(path[-1]["time"]).timestamp() * 1000) != exit_ms:
        raise RuntimeError(f"{trade['symbol']}: missing exit candle for {trade['exit_time']}")
    return path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True, type=Path)
    ap.add_argument("--out", default=Path("cap-diagnostic-results"), type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    summary, frame = load_inputs(args.artifact)
    symbols = list(dict.fromkeys(str(s).upper() for s in summary["symbols"]))
    if len(symbols) != 64:
        raise RuntimeError(f"Expected Run #160's 64-symbol snapshot, found {len(symbols)}")
    frame["signal_time"] = pd.to_datetime(frame["signal_time"], utc=True)
    frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True)
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    min_ms = utc_ms(frame["entry_time"].min()) - 24 * INTERVAL_MS
    max_ms = utc_ms(frame["exit_time"].max()) + 1
    print(f"Fetching hourly Spot klines for {len(symbols)} snapshot symbols...", flush=True)
    market = {}
    for idx, symbol in enumerate(symbols, 1):
        market[symbol] = fetch_klines(symbol, min_ms, max_ms)
        if idx % 8 == 0:
            print(f"Fetched {idx}/{len(symbols)} symbols", flush=True)
        time.sleep(0.12)

    # A signal stamped at candle open enters at the next hour open. At that
    # decision boundary, the just-closed signal candle plus prior 23 candles
    # form the trailing 24 completed hourly quote-volume buckets.
    universe_rank = {symbol: i for i, symbol in enumerate(symbols)}
    volume_rows = []
    volume_by_time_symbol = {}
    for signal_time, group in frame.groupby("signal_time", sort=True):
        decision_ms = utc_ms(group["entry_time"].iloc[0])
        window_start = decision_ms - 24 * INTERVAL_MS
        for symbol in symbols:
            bars = market[symbol]
            window = bars[(bars.close_ms < decision_ms) & (bars.close_ms >= window_start)]
            if len(window) != 24:
                raise RuntimeError(
                    f"Incomplete 24h quote-volume window: {symbol} at {signal_time}; "
                    f"found {len(window)} completed 1h candles"
                )
            qv = float(window["quote_volume"].sum())
            volume_by_time_symbol[(signal_time, symbol)] = qv
        candidates = group.to_dict("records")
        for trade in candidates:
            sym = str(trade["symbol"]).upper()
            qv = volume_by_time_symbol.get((signal_time, sym))
            if qv is None or not math.isfinite(qv) or qv <= 0:
                raise RuntimeError(f"Missing/invalid historical quote volume for {sym} at {signal_time}")
            volume_rows.append({
                "signal_time": signal_time.isoformat(), "symbol": sym,
                "quote_volume_24h_usdt": qv, "score": int(trade.get("score", 0) or 0),
                "strength": str(trade.get("strength", "")),
                "universe_snapshot_rank_tiebreak": universe_rank.get(sym, 9999)
            })

    volume_df = pd.DataFrame(volume_rows)
    # This mirrors main.sort_signals: score descending, STRONG before other
    # grades, stable order. get_scan_coins supplies that stable order by
    # 24h quote volume descending; original universe order breaks exact ties.
    rank_maps = {}
    selected = {3: [], 5: [], "uncapped": []}
    selection_rows = []
    for signal_time, group in frame.groupby("signal_time", sort=True):
        ranked = []
        for trade in group.to_dict("records"):
            sym = str(trade["symbol"]).upper()
            qv = volume_by_time_symbol[(signal_time, sym)]
            strong = 1 if str(trade.get("strength", "")) == "STRONG" else 0
            ranked.append((trade, qv, strong))
        ranked.sort(key=lambda x: (
            -int(x[0].get("score", 0) or 0), -x[2], -x[1],
            universe_rank.get(str(x[0]["symbol"]).upper(), 9999)
        ))
        for i, (trade, qv, strong) in enumerate(ranked, 1):
            selection_rows.append({
                "signal_time": signal_time.isoformat(), "rank": i,
                "symbol": trade["symbol"], "score": trade["score"],
                "strength": trade["strength"], "quote_volume_24h_usdt": qv,
                "selected_cap3": i <= 3, "selected_cap5": i <= 5,
                "selected_uncapped": True
            })
            for cap in (3, 5, "uncapped"):
                if cap == "uncapped" or i <= cap:
                    selected[cap].append(trade)

    # Reconstruct exact hourly MTM paths for all 135 candidates. Fail closed
    # rather than substitute a constant/exit-only path.
    candidates_with_paths = []
    for trade in frame.to_dict("records"):
        t = dict(trade)
        t["_path"] = make_path(t, market[str(t["symbol"]).upper()])
        candidates_with_paths.append(t)

    # Preserve selected row identities by (signal_time, symbol); no duplicate
    # symbol candidates exist at a single timestamp in this stream.
    by_key = {(pd.Timestamp(t["signal_time"]), str(t["symbol"])): t for t in candidates_with_paths}
    baseline = summary["engine_only_portfolio_comparison"]["REVERSAL"]
    results = {}
    for cap in (3, 5, "uncapped"):
        chosen = selected[cap]
        replay = [by_key[(pd.Timestamp(t["signal_time"]), str(t["symbol"]))] for t in chosen]
        out_dir = args.out / ("cap3" if cap == 3 else "cap5" if cap == 5 else "uncapped")
        result = portfolio_ledger(replay, out_dir, initial_cash=1000.0,
                                  risk_pct=1.0, max_position_pct=100.0)
        results[str(cap)] = result

    uncapped = results["uncapped"]
    checks = {
        "final_equity_match": abs(float(uncapped["final_equity_usdt"]) - float(baseline["final_equity_usdt"])) <= 0.01,
        "max_drawdown_match": abs(float(uncapped["max_drawdown_pct"]) - float(baseline["max_drawdown_pct"])) <= 0.01,
        "accepted_count_match": int(uncapped["accepted_trades"]) == int(baseline["accepted_trades"]),
        "rejected_count_match": int(uncapped["rejected_trades"]) == int(baseline["rejected_trades"]),
    }
    validation = "PASS" if all(checks.values()) else "FAIL"
    (args.out / "volume_rank_audit.csv").write_text(volume_df.to_csv(index=False), encoding="utf-8")
    pd.DataFrame(selection_rows).to_csv(args.out / "candidate_selection.csv", index=False)
    compact = {
        "source_run_id": RUN_ID, "source_artifact_id": ARTIFACT_ID,
        "source_commit": "c904044124938048df7507095158cd1423d2044c",
        "candidate_stream": "REVERSAL / BOTTOM_HUNTER only",
        "universe_symbols": len(symbols), "candidate_rows": len(frame),
        "volume_method": "sum of 24 completed 1h Binance Spot quote-asset-volume buckets at the next-hour decision boundary",
        "selection_method": "production sort_signals score desc, STRONG first, stable order from historical quote-volume rank",
        "account": {"initial_usdt": 1000, "risk_pct": 1, "max_position_pct": 100,
                    "fee_and_slippage_and_exit_rules": "inherited from Run #160 candidate trades"},
        "baseline_reproduction": {"status": validation, "checks": checks,
                                  "expected": {k: baseline[k] for k in (
                                      "final_equity_usdt","net_pnl_usdt","max_drawdown_pct",
                                      "candidate_trades","accepted_trades","rejected_trades")},
                                  "replayed": {k: uncapped[k] for k in (
                                      "final_equity_usdt","net_pnl_usdt","max_drawdown_pct",
                                      "candidate_trades","accepted_trades","rejected_trades")}},
        "cap_results": results,
        "interpretation": (
            "Cap comparisons are validated only if baseline_reproduction.status is PASS. "
            "No source/live settings are modified by this diagnostic."
        )
    }
    (args.out / "summary.json").write_text(json.dumps(compact, indent=2, default=str), encoding="utf-8")
    print(json.dumps(compact["baseline_reproduction"], indent=2), flush=True)
    if validation != "PASS":
        raise SystemExit("Baseline replay did not reproduce Run #160; do not use cap results.")
    print("CAP DIAGNOSTIC COMPLETE: baseline reproduced; cap3/cap5/uncapped outputs saved.", flush=True)

if __name__ == "__main__":
    main()
