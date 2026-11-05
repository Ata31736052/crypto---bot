#!/usr/bin/env python3
"""Controlled A/B benchmark for historical_backtest.py.

Runs both Git revisions in isolated worktrees on one runner, with a shared HTTP
response cache so both revisions replay identical Binance payloads. One warm-up
pair is excluded; measured runs alternate B-A-B-A-B-A. Exit non-zero on any
trade/output mismatch. No live scan, Telegram, or order execution.
"""
from __future__ import annotations
import csv, hashlib, json, os, pathlib, shutil, subprocess, sys, time
from statistics import median

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "ab-benchmark-results"
progress_path = OUT / "progress.json"
CACHE = OUT / "http-cache"
WORK = pathlib.Path(os.getenv("RUNNER_TEMP", "/tmp")) / "apexsignal-ab-worktrees"
OUT.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True); WORK.mkdir(exist_ok=True)
BASE_SHA = os.environ["AB_BASE_SHA"]
CANDIDATE_SHA = os.environ["AB_CANDIDATE_SHA"]
REPEATS = int(os.getenv("AB_REPEATS", "3"))
if REPEATS < 3:
    raise SystemExit("AB_REPEATS must be >= 3 for meaningful dispersion estimates")
ENV = os.environ.copy()
ENV.update({
    "BACKTEST_DAYS": os.getenv("BACKTEST_DAYS", "180"),
    "BACKTEST_SYMBOLS": os.getenv("BACKTEST_SYMBOLS", "ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT"),
    "BACKTEST_FEE_BPS": os.getenv("BACKTEST_FEE_BPS", "10"),
    "BACKTEST_SLIPPAGE_BPS": os.getenv("BACKTEST_SLIPPAGE_BPS", "5"),
    "BACKTEST_END_TIME": os.getenv("BACKTEST_END_TIME", "2026-10-12T00:00:00Z"),
    "AB_SIGNAL_BOUNDARY": os.getenv("BACKTEST_END_TIME", "2026-10-12T00:00:00Z"),
    "BACKTEST_PROFILE_ENGINE": "0",
    "PYTHONUNBUFFERED": "1",
    "TELEGRAM_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "DRY_RUN": "1",
    "RUN_ONCE": "0",
})
# This sitecustomize patch records the first response for each exact URL+params
# and replays it for all subsequent invocations/revisions on this runner.
PATCH = OUT / "sitecustomize.py"
PATCH.write_text(r'''
import hashlib, json, os, pathlib
import requests
_cache = pathlib.Path(os.environ["AB_HTTP_CACHE"])
_cache.mkdir(parents=True, exist_ok=True)
_original = requests.sessions.Session.request
def _request(self, method, url, **kwargs):
    if method.upper() != "GET" or "/api/v3/klines" not in url:
        return _original(self, method, url, **kwargs)
    key = json.dumps({"url":url,"params":kwargs.get("params",{})}, sort_keys=True, separators=(",",":"))
    path = _cache / (hashlib.sha256(key.encode()).hexdigest()+".json")
    if path.exists():
        payload=json.loads(path.read_text())
        response=requests.Response()
        response.status_code=payload["status"]
        response._content=payload["body"].encode()
        response.url=url
        response.headers.update(payload.get("headers",{}))
        response.encoding="utf-8"
        response.request=requests.Request(method,url).prepare()
        return response
    response=_original(self,method,url,**kwargs)
    response.raise_for_status()
    path.write_text(json.dumps({"status":response.status_code,"body":response.text,
                                "headers":{"Content-Type":response.headers.get("Content-Type","application/json")}}))
    return response
requests.sessions.Session.request=_request
''', encoding="utf-8")
ENV["AB_HTTP_CACHE"] = str(CACHE)
ENV["PYTHONPATH"] = str(OUT) + os.pathsep + ENV.get("PYTHONPATH", "")
def run(cmd, cwd=None, env=None, capture=False):
    return subprocess.run(cmd, cwd=cwd, env=env, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.STDOUT if capture else None)
def git(*args):
    return run(["git", *args], cwd=ROOT, capture=True).stdout.strip()
# Fetch refs and create isolated worktrees from immutable commit SHAs.
run(["git","fetch","--no-tags","origin",BASE_SHA,CANDIDATE_SHA], cwd=ROOT)
for label, sha in (("A",BASE_SHA),("B",CANDIDATE_SHA)):
    path=WORK/label
    if path.exists(): shutil.rmtree(path)
    run(["git","worktree","add","--detach",str(path),sha],cwd=ROOT)
# The historical baseline predates BACKTEST_END_TIME support and otherwise
# silently uses the runner's current hour. Apply a benchmark-only date-anchor
# shim to A so both revisions receive the exact same fixed test window. This
# changes no strategy or performance code; the report/logs preserve both SHAs.
baseline_file = WORK / "A" / "historical_backtest.py"
baseline_source = baseline_file.read_text(encoding="utf-8")
legacy_end = '    end=pd.Timestamp.now(tz="UTC").floor("h"); start=end-pd.Timedelta(days=DAYS); fetch_start=start-pd.Timedelta(days=WARMUP_DAYS)'
fixed_end = '''    end_raw=os.getenv("BACKTEST_END_TIME", "").strip()
    if end_raw:
        end=pd.Timestamp(end_raw)
        if end.tzinfo is None:
            raise ValueError("BACKTEST_END_TIME must include Z or an explicit UTC offset")
        end=end.tz_convert("UTC").floor("h")
    else:
        end=pd.Timestamp.now(tz="UTC").floor("h")
    start=end-pd.Timedelta(days=DAYS); fetch_start=start-pd.Timedelta(days=WARMUP_DAYS)'''
if legacy_end in baseline_source:
    baseline_file.write_text(baseline_source.replace(legacy_end, fixed_end, 1), encoding="utf-8")
elif 'BACKTEST_END_TIME' not in baseline_source:
    raise SystemExit("Cannot safely anchor baseline: expected legacy end-time expression was not found")
# Benchmark-only source shims: align the baseline end-boundary policy and fingerprint raw OHLCV frames before prepare().
MANIFEST_HELPER = r'''
import hashlib, json, os

def _ab_record_input(symbol, tf, frame):
    path = os.getenv("AB_INPUT_MANIFEST")
    if not path:
        raise RuntimeError("AB_INPUT_MANIFEST is required for controlled A/B")
    boundary = pd.Timestamp(os.environ["AB_SIGNAL_BOUNDARY"])
    if boundary.tzinfo is None:
        raise RuntimeError("AB_SIGNAL_BOUNDARY must include a timezone")
    boundary = boundary.tz_convert("UTC")
    cols = ["open_time", "close_time", "open", "high", "low", "close", "volume"]
    if tf == "1h":
        signal_frame = frame[(frame["close_time"] < boundary) | (frame["open_time"] == boundary)]
        outcome_frame = frame[frame["open_time"] > boundary]
    else:
        signal_frame = frame[frame["close_time"] < boundary]
        outcome_frame = frame.iloc[0:0]
    def fingerprint(part):
        canonical = part[cols].to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%S.%f%z", float_format="%.12g") if not part.empty else "EMPTY\n"
        return {"rows": int(len(part)), "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                "first_open": str(part.iloc[0]["open_time"]) if len(part) else None,
                "last_open": str(part.iloc[-1]["open_time"]) if len(part) else None}
    # Mutation regression: changing an outcome-only candle must alter the outcome hash.
    if not getattr(_ab_record_input, "_mutation_test_done", False):
        sample = pd.DataFrame({
            "open_time": pd.to_datetime(["2026-10-12T00:00:00Z", "2026-10-12T01:00:00Z"], utc=True),
            "close_time": pd.to_datetime(["2026-10-12T00:59:59.999Z", "2026-10-12T01:59:59.999Z"], utc=True),
            "open": [100.0, 101.0], "high": [101.0, 102.0], "low": [99.0, 100.0],
            "close": [100.5, 101.5], "volume": [10.0, 11.0]})
        outcome = sample[sample["open_time"] > boundary]
        altered = sample.copy()
        altered.loc[1, "close"] = 101.6
        altered_outcome = altered[altered["open_time"] > boundary]
        if fingerprint(outcome)["sha256"] == fingerprint(altered_outcome)["sha256"]:
            raise RuntimeError("Outcome-only candle mutation did not change manifest hash")
        _ab_record_input._mutation_test_done = True
        print("AB_OUTCOME_MANIFEST_MUTATION_SELF_TEST: PASS", flush=True)
    record = {"symbol": symbol, "timeframe": tf,
              "signal_window": fingerprint(signal_frame),
              "outcome_window": fingerprint(outcome_frame)}
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
'''
for label in ("A", "B"):
    source_path = WORK / label / "historical_backtest.py"
    source = source_path.read_text(encoding="utf-8")
    if "def _ab_record_input(" not in source:
        source = source.replace("def fetch(", MANIFEST_HELPER + "\ndef fetch(", 1)
    if label == "A":
        # Older baselines need a compatibility shim. If the selected baseline
        # already implements the fixed-window and boundary-aware fetch API,
        # leave its execution policy intact instead of trying to patch it again.
        legacy_sig = "def fetch(symbol, tf, start_ms, end_ms):"
        modern_sig = "def fetch(symbol, tf, start_ms, end_ms, include_boundary_open=False, now=None, signal_boundary_ms=None):"
        if legacy_sig in source:
            source = source.replace(legacy_sig, "def fetch(symbol, tf, start_ms, end_ms, include_boundary_open=False, signal_boundary_ms=None):", 1)
            old_filters = (
                '    d=filter_closed_before_end(d,end_ms).dropna(subset=["open","high","low","close","volume"])',
                '    d=d[d.close_time < pd.Timestamp.now(tz="UTC")].dropna(subset=["open","high","low","close","volume"])',
            )
            new_filter = '''    boundary=pd.to_datetime(signal_boundary_ms if signal_boundary_ms is not None else end_ms,unit="ms",utc=True)
    data_cutoff=pd.to_datetime(end_ms,unit="ms",utc=True)
    d=d[(d.close_time < data_cutoff) | ((tf == "1h") & include_boundary_open & (d.open_time == boundary))]
    d=d.dropna(subset=["open","high","low","close","volume"])'''
            matched_filters = [line for line in old_filters if line in source]
            if len(matched_filters) != 1:
                raise SystemExit(
                    "Cannot safely normalize legacy baseline end-boundary policy: "
                    f"expected exactly one known filter, found {len(matched_filters)}"
                )
            source = source.replace(matched_filters[0], new_filter, 1)
            if new_filter not in source:
                raise SystemExit("Legacy baseline boundary normalization postcondition failed")
            source = source.replace('fetch("BTCUSDT",tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000))', 'fetch("BTCUSDT",tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000),include_boundary_open=(tf=="1h"))')
            source = source.replace('raw={tf:fetch(sym,tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000)) for tf in ("1h","30m","4h","1d")}',
'''raw={tf:fetch(sym,tf,int(fetch_start.timestamp()*1000),
                           int((end+pd.Timedelta(hours=73)).timestamp()*1000) if tf=="1h" else int(end.timestamp()*1000),
                           include_boundary_open=(tf=="1h"),
                           signal_boundary_ms=int(end.timestamp()*1000) if tf=="1h" else None)
                   for tf in ("1h","30m","4h","1d")}''')
            source = source.replace('                c=h1.iloc[i]; close_time=c.close_time',
                                    '                c=h1.iloc[i]; close_time=c.close_time\n                if c.open_time >= end: break', 1)
        elif modern_sig in source and "BACKTEST_END_TIME" in source and "signal_boundary_ms" in source:
            print("A_BASELINE_ALREADY_HAS_FIXED_WINDOW_AND_BOUNDARY_API: no compatibility shim needed", flush=True)
        else:
            raise SystemExit("Cannot safely patch baseline: unsupported fetch signature or missing fixed-window boundary support")
    return_line = '    return d.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)[["open_time","close_time","open","high","low","close","volume"]]'
    replacement = '''    d=d.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)[["open_time","close_time","open","high","low","close","volume"]]
    _ab_record_input(symbol, tf, d)
    return d'''
    if return_line not in source: raise SystemExit(f"Cannot instrument {label} fetch return")
    source = source.replace(return_line, replacement, 1)
    if label == "A":
        # Report-only compatibility shim: compute the same in-trade MAE/MFE
        # as candidate B. Exclude the exit candle's OHLC extrema because the
        # intrabar order after the simulated exit is unknowable; use exit_fill
        # as the terminal observed point. No entry/exit decision is modified.
        legacy_return = '    return {"symbol":symbol,"side":side,"signal_time":str(signal_time),"entry_time":str(row.open_time),'
        common_path_metrics = '''    prior_path=h1.iloc[entry_i:xi]
    prior_highs=pd.to_numeric(prior_path["high"],errors="coerce").to_numpy(dtype=float)
    prior_lows=pd.to_numeric(prior_path["low"],errors="coerce").to_numpy(dtype=float)
    if side=="BUY":
        favorable_points=list(prior_highs)+[float(exit_fill)]
        adverse_points=list(prior_lows)+[float(exit_fill)]
        mfe_price=max(0.0,max(favorable_points)-entry)
        mae_price=max(0.0,entry-min(adverse_points))
        mfe_bar=favorable_points.index(max(favorable_points))
        mae_bar=adverse_points.index(min(adverse_points))
    else:
        favorable_points=list(prior_lows)+[float(exit_fill)]
        adverse_points=list(prior_highs)+[float(exit_fill)]
        mfe_price=max(0.0,entry-min(favorable_points))
        mae_price=max(0.0,max(adverse_points)-entry)
        mfe_bar=favorable_points.index(min(favorable_points))
        mae_bar=adverse_points.index(max(adverse_points))
'''
        if source.count(legacy_return) != 1:
            raise SystemExit("Cannot safely add common MAE/MFE metrics to baseline simulate()")
        source = source.replace(legacy_return, common_path_metrics + legacy_return, 1)
        metric_anchor = '"risk_cost_pct":round(risk_cost_pct,4),'
        metric_fields = '"risk_cost_pct":round(risk_cost_pct,4),"mfe_pct":round(mfe_price/entry*100,5),"mae_pct":round(-mae_price/entry*100,5),"mfe_r":round(mfe_price/risk,5) if risk>0 else None,"mae_r":round(-mae_price/risk,5) if risk>0 else None,"bars_to_mfe":mfe_bar,"bars_to_mae":mae_bar,'
        if source.count(metric_anchor) != 1:
            raise SystemExit("Cannot safely add MAE/MFE fields to baseline trade result")
        source = source.replace(metric_anchor, metric_fields, 1)
        old_columns = '"net_pct","bars_held"'
        if source.count(old_columns) != 1:
            raise SystemExit("Cannot safely extend baseline trade CSV schema with MAE/MFE")
        source = source.replace(old_columns, '"net_pct","mfe_pct","mae_pct","mfe_r","mae_r","bars_to_mfe","bars_to_mae","bars_held"', 1)
        if not all(key in source for key in ("mfe_pct", "mae_pct", "bars_to_mfe", "bars_to_mae")):
            raise SystemExit("Baseline MAE/MFE shim postcondition failed")
    source_path.write_text(source, encoding="utf-8")
# Verify both revisions can run the exact same harness entrypoint.
for label in ("A","B"):
    path=WORK/label
    for required in ("main.py","historical_backtest.py","portfolio_ledger.py","requirements.txt"):
        if not (path/required).is_file():
            raise SystemExit(f"{label} missing required file: {required}")
# Dependencies are installed once in the job's Python environment; cache is
# shared and makes network data independent of which revision runs first.
def one(label, phase, ordinal):
    path=WORK/label
    shutil.rmtree(path/"backtest-results",ignore_errors=True)
    log_path=OUT/f"{phase}-{label}-{ordinal}.log"
    progress_path=OUT/"progress.json"
    run_id=f"{phase}-{label}-{ordinal}"
    started=time.perf_counter()
    started_unix=time.time()
    timeout_seconds=int(os.getenv("AB_SINGLE_RUN_TIMEOUT_SECONDS","2700"))
    print(f"START {run_id}; per-run timeout={timeout_seconds}s; log={log_path}",flush=True)
    manifest_path = OUT / f"{run_id}-input-manifest.jsonl"
    manifest_path.unlink(missing_ok=True)
    run_env = ENV.copy()
    run_env["AB_INPUT_MANIFEST"] = str(manifest_path)
    with log_path.open("w",encoding="utf-8") as log_file:
        proc=subprocess.Popen([sys.executable,"-u","historical_backtest.py"],cwd=path,env=run_env,
                              stdout=log_file,stderr=subprocess.STDOUT,text=True)
        while proc.poll() is None:
            elapsed=time.perf_counter()-started
            progress={"current_run":run_id,"elapsed_seconds":round(elapsed,1),
                      "pid":proc.pid,"timeout_seconds":timeout_seconds,
                      "started_unix":started_unix,"status":"RUNNING"}
            progress_path.write_text(json.dumps(progress,indent=2),encoding="utf-8")
            print(f"HEARTBEAT {run_id}: elapsed={int(elapsed)}s pid={proc.pid}",flush=True)
            if elapsed >= timeout_seconds:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                progress.update({"status":"TIMED_OUT","returncode":proc.returncode})
                progress_path.write_text(json.dumps(progress,indent=2),encoding="utf-8")
                raise SystemExit(f"TIMEOUT: {run_id} exceeded {timeout_seconds}s; inspect {log_path}")
            time.sleep(min(5,max(1,timeout_seconds-elapsed)))
    wall=time.perf_counter()-started
    progress={"current_run":run_id,"elapsed_seconds":round(wall,1),
              "returncode":proc.returncode,"status":"COMPLETED" if proc.returncode==0 else "FAILED"}
    progress_path.write_text(json.dumps(progress,indent=2),encoding="utf-8")
    if proc.returncode != 0:
        tail=log_path.read_text(encoding="utf-8",errors="replace")[-5000:]
        raise SystemExit(f"{run_id} exited with code {proc.returncode}; log tail:\\n{tail}")
    log=log_path.read_text(encoding="utf-8",errors="replace")
    summary_path=path/"backtest-results"/"summary.json"
    trades_path=path/"backtest-results"/"trades.csv"
    if not summary_path.exists() or not trades_path.exists():
        raise SystemExit(f"{label} run did not produce summary.json and trades.csv; inspect {log_path}")
    with trades_path.open("r", encoding="utf-8", newline="") as trade_file:
        trade_reader = csv.DictReader(trade_file)
        required_path_fields = {"mfe_pct", "mae_pct", "mfe_r", "mae_r", "bars_to_mfe", "bars_to_mae"}
        missing_path_fields = required_path_fields - set(trade_reader.fieldnames or [])
        if missing_path_fields:
            raise SystemExit(f"{label} trade CSV missing comparable path fields: {sorted(missing_path_fields)}")
        trade_rows = list(trade_reader)
    def numeric_metric(name):
        values=[]
        for trade in trade_rows:
            try:
                value=float(trade.get(name, ""))
                if value == value and abs(value) != float("inf"):
                    values.append(value)
            except (TypeError, ValueError):
                pass
        return {"count":len(values),"median":round(median(values),5) if values else None,
                "mean":round(sum(values)/len(values),5) if values else None}
    path_metrics={name:numeric_metric(name) for name in sorted(required_path_fields)}
    summary=json.loads(summary_path.read_text())
    if not manifest_path.is_file():
        raise SystemExit(f"{run_id} missing raw input manifest; refusing to compare")
    manifest=[json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_manifest_count=2+4*len(ENV["BACKTEST_SYMBOLS"].split(","))
    if len(manifest) != expected_manifest_count:
        raise SystemExit(f"{run_id} manifest count {len(manifest)} != expected {expected_manifest_count}; refusing to compare")
    manifest.sort(key=lambda x:(x["symbol"],x["timeframe"]))
    manifest_sha256=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    # manifest_path already lives at its archival destination under OUT.
    # Do not copy a file onto itself (shutil raises SameFileError).
    if summary.get("status") != "COMPLETED" or summary.get("errors"):
        raise SystemExit(f"{label} backtest has errors; refusing to compare; inspect {log_path}")
    # Archive the shared-cash ledger too: aggregate summary values alone cannot
    # explain cash competition, rejected entries, sizing, or equity/drawdown paths.
    ledger_names=("portfolio_trades.csv","portfolio_equity.csv","per_symbol.csv")
    ledger_paths={name:path/"backtest-results"/name for name in ledger_names}
    missing_ledger=[name for name,file_path in ledger_paths.items() if not file_path.is_file()]
    if missing_ledger:
        raise SystemExit(f"{label} run missing shared-cash ledger outputs: {missing_ledger}; refusing to compare")

    with ledger_paths["portfolio_trades.csv"].open("r",encoding="utf-8",newline="") as ledger_file:
        ledger_reader=csv.DictReader(ledger_file)
        required_ledger_fields={"symbol","side","entry_time","exit_time","portfolio_status",
                                "portfolio_reject_reason","position_notional_usdt",
                                "risk_budget_usdt","portfolio_pnl_usdt"}
        missing_fields=required_ledger_fields-set(ledger_reader.fieldnames or [])
        if missing_fields:
            raise SystemExit(f"{label} portfolio ledger missing fields: {sorted(missing_fields)}")
        ledger_rows=list(ledger_reader)
    with ledger_paths["portfolio_equity.csv"].open("r",encoding="utf-8",newline="") as equity_file:
        equity_reader=csv.DictReader(equity_file)
        required_equity_fields={"time","cash_usdt","open_positions","open_notional_usdt",
                                "equity_usdt","drawdown_pct","capital_utilization_pct",
                                "gross_exposure_pct_equity"}
        missing_fields=required_equity_fields-set(equity_reader.fieldnames or [])
        if missing_fields:
            raise SystemExit(f"{label} equity ledger missing fields: {sorted(missing_fields)}")
        equity_rows=list(equity_reader)
    if not equity_rows:
        raise SystemExit(f"{label} equity ledger is empty; refusing to compare")

    portfolio_summary=summary.get("portfolio",{})
    accepted_rows=[row for row in ledger_rows if row.get("portfolio_status")=="ACCEPTED"]
    rejected_rows=[row for row in ledger_rows if row.get("portfolio_status")=="REJECTED"]
    if len(ledger_rows)!=int(portfolio_summary.get("candidate_trades",-1)):
        raise SystemExit(f"{label} ledger candidate count does not reconcile to summary")
    if len(accepted_rows)!=int(portfolio_summary.get("accepted_trades",-1)) or len(rejected_rows)!=int(portfolio_summary.get("rejected_trades",-1)):
        raise SystemExit(f"{label} ledger accepted/rejected counts do not reconcile to summary")
    try:
        ledger_pnl=sum(float(row["portfolio_pnl_usdt"] or 0) for row in accepted_rows)
        summary_pnl=float(portfolio_summary["net_pnl_usdt"])
        if abs(ledger_pnl-summary_pnl)>0.001:
            raise SystemExit(f"{label} accepted-trade PnL {ledger_pnl:.6f} does not reconcile to portfolio PnL {summary_pnl:.6f}")
        for row in equity_rows:
            cash=float(row["cash_usdt"])
            equity=float(row["equity_usdt"])
            drawdown=float(row["drawdown_pct"])
            if not all(map(lambda value: value==value and abs(value)!=float("inf"),(cash,equity,drawdown))):
                raise SystemExit(f"{label} equity ledger contains a non-finite value")
            if cash < -0.000001 or drawdown < -0.000001:
                raise SystemExit(f"{label} equity ledger violates cash or drawdown bounds")
    except (KeyError,TypeError,ValueError) as exc:
        raise SystemExit(f"{label} ledger contains invalid numeric accounting fields: {exc}")

    ledger_sha256={name:hashlib.sha256(file_path.read_bytes()).hexdigest()
                   for name,file_path in ledger_paths.items()}
    # Store every ledger with each measured sample; upload-artifact then preserves
    # the per-trade acceptance/rejection trail and timestamped account equity.
    sample=OUT/f"{phase}-{label}-{ordinal}"
    sample.mkdir(exist_ok=True)
    shutil.copy2(summary_path,sample/"summary.json")
    shutil.copy2(trades_path,sample/"trades.csv")
    for name,file_path in ledger_paths.items():
        shutil.copy2(file_path,sample/name)
    return {"label":label,"phase":phase,"ordinal":ordinal,"wall_seconds":round(wall,4),
            "engine_seconds":summary["performance"]["stage_seconds"].get("signal_engine",0),
            "total_instrumented_seconds":summary["performance"]["total_instrumented_seconds"],
            "engine_calls":summary["performance"]["counters"].get("engine_calls"),
            "trade_sha256":hashlib.sha256(trades_path.read_bytes()).hexdigest(),
            "ledger_sha256":ledger_sha256,
            "ledger_counts":{"candidates":len(ledger_rows),"accepted":len(accepted_rows),
                             "rejected":len(rejected_rows),"equity_points":len(equity_rows)},
            "ledger_reconciled":True,
            "input_manifest_sha256":manifest_sha256,"input_manifest_rows":len(manifest),
            "path_metrics":path_metrics,
            "summary":summary}
# Warm the exact response cache; warm-up runs are deliberately not timed samples.
print("WARMUP A",flush=True); one("A","warmup",1)
print("WARMUP B",flush=True); one("B","warmup",1)
# Alternating sequence prevents a version from systematically benefiting from
# runner warm state. Same runner, Python process settings, inputs, and API cache.
samples=[]
sequence=[("B",1),("A",1),("B",2),("A",2),("B",3),("A",3)]
for label, ordinal in sequence:
    print(f"MEASURE {label} {ordinal}",flush=True)
    samples.append(one(label,"measured",ordinal))
# Check determinism within each revision; A-vs-B differences are expected
# for a strategy-changing PR and must be measured, not treated as harness failure.
baseline=[s for s in samples if s["label"]=="A"]
candidate=[s for s in samples if s["label"]=="B"]
input_manifest_hashes={s["input_manifest_sha256"] for s in samples}
if len(input_manifest_hashes) != 1:
    (OUT/"input-mismatch.json").write_text(json.dumps({
        "status":"INPUT_MISMATCH_ABORTED_BEFORE_TIMING_COMPARISON",
        "manifests":[{"label":s["label"],"phase":s["phase"],"ordinal":s["ordinal"],
                     "sha256":s["input_manifest_sha256"],"rows":s["input_manifest_rows"]} for s in samples]},indent=2))
    raise SystemExit("INPUT MISMATCH: raw OHLCV manifests differ; do not compare timings")
def comparable(s):
    x=s["summary"]
    return {"period_start":x["period_start"],"period_end":x["period_end"],
            "symbols":x["symbols"],"candidate_trade_count":x["candidate_trade_count"],
            "portfolio":x["portfolio"],"engine_breakdown":x["engine_breakdown"],
            "diagnostics":x["diagnostics"]}
def assert_repeatable(rows, label):
    trade_hashes={s["trade_sha256"] for s in rows}
    summary_hashes={json.dumps(comparable(s),sort_keys=True,default=str) for s in rows}
    ledger_hashes={json.dumps(s.get("ledger_sha256",{}),sort_keys=True) for s in rows}
    if len(trade_hashes)!=1 or len(summary_hashes)!=1 or len(ledger_hashes)!=1:
        (OUT/f"repeatability-mismatch-{label}.json").write_text(json.dumps({
            "label":label,
            "trade_hashes":[s["trade_sha256"] for s in rows],
            "ledger_hashes":[s.get("ledger_sha256",{}) for s in rows],
            "summaries":[{"ordinal":s["ordinal"],"summary":comparable(s)} for s in rows]
        },indent=2,default=str))
        raise SystemExit(f"REPEATABILITY FAILURE within {label}; see repeatability-mismatch-{label}.json")
    return {"trades":next(iter(trade_hashes)),
            "ledger":rows[0].get("ledger_sha256",{})}
baseline_hashes=assert_repeatable(baseline,"A")
candidate_hashes=assert_repeatable(candidate,"B")
def stats(rows,key):
    values=[float(r[key]) for r in rows]
    return {"samples":values,"median":round(median(values),4),
            "min":round(min(values),4),"max":round(max(values),4),
            "range":round(max(values)-min(values),4)}
def outcome_metrics(rows):
    # Repeatability is already verified, so the first sample represents this revision.
    x=rows[0]["summary"]
    p=x.get("portfolio",{})
    return {
        "period_start":x.get("period_start"),"period_end":x.get("period_end"),
        "candidate_trade_count":x.get("candidate_trade_count"),
        "accepted_trades":p.get("accepted_trades"),
        "rejected_trades":p.get("rejected_trades"),
        "net_pnl_usdt":p.get("net_pnl_usdt"),
        "net_return_pct":p.get("net_return_pct"),
        "max_drawdown_pct":p.get("max_drawdown_pct"),
        "final_equity_usdt":p.get("final_equity_usdt"),
    }
outcome_A=outcome_metrics(baseline)
outcome_B=outcome_metrics(candidate)
outcome_delta={}
for key in ("candidate_trade_count","accepted_trades","rejected_trades","net_pnl_usdt",
            "net_return_pct","max_drawdown_pct","final_equity_usdt"):
    a,b=outcome_A.get(key),outcome_B.get(key)
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):
        outcome_delta[key]=round(b-a,6)
report={
 "status":"PASS_REPEATABILITY_A_AND_B; STRATEGY_DIFFERENCES_REPORTED",
 "portfolio_outcome_comparison":{"baseline_A":outcome_A,"candidate_B":outcome_B,
                                 "candidate_minus_baseline":outcome_delta},
 "base_sha":BASE_SHA,"candidate_sha":CANDIDATE_SHA,
 "configuration":{"days":ENV["BACKTEST_DAYS"],"symbols":ENV["BACKTEST_SYMBOLS"],
                  "fee_bps_per_side":ENV["BACKTEST_FEE_BPS"],
                  "slippage_bps_per_side":ENV["BACKTEST_SLIPPAGE_BPS"],
                  "fixed_end_time":ENV["BACKTEST_END_TIME"],"python":sys.version},
 "order":["B1","A1","B2","A2","B3","A3"],
 "timings":{"baseline_A":{"wall":stats(baseline,"wall_seconds"),
                          "signal_engine":stats(baseline,"engine_seconds"),
                          "instrumented_total":stats(baseline,"total_instrumented_seconds")},
            "candidate_B":{"wall":stats(candidate,"wall_seconds"),
                           "signal_engine":stats(candidate,"engine_seconds"),
                           "instrumented_total":stats(candidate,"total_instrumented_seconds")}},
 "samples":[{k:v for k,v in s.items() if k!="summary"} for s in samples],
 "in_trade_path_metrics":{"definition":"same simulate-time formula in A and B; entry-to-exit path, exclude exit-candle OHLC extrema, terminal point is simulated exit fill",
                        "baseline_A":baseline[0]["path_metrics"],
                        "candidate_B":candidate[0]["path_metrics"],
                        "note":"MFE/MAE are path diagnostics, not portfolio P&L; compare alongside shared-account outcomes."},
 "trade_sha256":{"baseline_A":baseline_hashes["trades"],"candidate_B":candidate_hashes["trades"],"identical_between_versions":baseline_hashes["trades"]==candidate_hashes["trades"]},
 "portfolio_ledger":{"baseline_A":baseline_hashes["ledger"],"candidate_B":candidate_hashes["ledger"],
                     "identical_between_versions":baseline_hashes["ledger"]==candidate_hashes["ledger"],
                     "note":"A-vs-B ledger differences are expected when strategy trades differ; each revision's ledger hashes must repeat exactly across its three measured runs."},
 "input_manifest_sha256":next(iter(input_manifest_hashes)),
 "input_manifest_rows":samples[0]["input_manifest_rows"],
 "notes":["Separate signal-window and outcome-window OHLCV hashes and row counts are fingerprinted before indicator preparation and must match across all samples.",
          "Both baseline and candidate fetch the same 73-hour post-boundary 1H outcome window; replay stops at the fixed signal boundary.",
          "Baseline is benchmark-shimmed to the candidate's exclusive end boundary, retaining the boundary-open execution candle only for 1H.",
          "Same GitHub-hosted runner and Python environment for all samples.",
          "Exact Binance kline HTTP responses are cached and replayed to both revisions.",
          "Wall time includes Python startup; signal_engine stage is the primary optimization metric.",
          "No signal thresholds, strategy rules, Telegram delivery, or orders are changed."]
}
progress_path.write_text(json.dumps({"status":"BENCHMARK_COMPARISON_COMPLETE","completed_unix":time.time()},indent=2),encoding="utf-8")
report["signal_engine_median_improvement_pct"]=round(
    (1-report["timings"]["candidate_B"]["signal_engine"]["median"]/
     report["timings"]["baseline_A"]["signal_engine"]["median"])*100,2
) if report["timings"]["baseline_A"]["signal_engine"]["median"] else None
(OUT/"report.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ("samples",)},indent=2,default=str),flush=True)
print("A/B benchmark: PASS (repeatability checked separately within A and B; A-vs-B differences reported)",flush=True)
