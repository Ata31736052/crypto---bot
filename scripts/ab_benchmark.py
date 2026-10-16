#!/usr/bin/env python3
"""Controlled A/B benchmark for historical_backtest.py.

Runs both Git revisions in isolated worktrees on one runner, with a shared HTTP
response cache so both revisions replay identical Binance payloads. One warm-up
pair is excluded; measured runs alternate B-A-B-A-B-A. Exit non-zero on any
trade/output mismatch. No live scan, Telegram, or order execution.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, shutil, subprocess, sys, time
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
    "BACKTEST_END_TIME": os.getenv("BACKTEST_END_TIME", "2026-10-13T13:00:00Z"),
    "AB_SIGNAL_BOUNDARY": os.getenv("BACKTEST_END_TIME", "2026-10-13T13:00:00Z"),
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
        sig = "def fetch(symbol, tf, start_ms, end_ms):"
        if sig not in source: raise SystemExit("Cannot safely patch baseline fetch signature")
        source = source.replace(sig, "def fetch(symbol, tf, start_ms, end_ms, include_boundary_open=False, signal_boundary_ms=None):", 1)
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
                "Cannot safely normalize baseline end-boundary policy: "
                f"expected exactly one known filter, found {len(matched_filters)}"
            )
        source = source.replace(matched_filters[0], new_filter, 1)
        if new_filter not in source:
            raise SystemExit("Baseline boundary normalization postcondition failed")
        source = source.replace('fetch("BTCUSDT",tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000))', 'fetch("BTCUSDT",tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000),include_boundary_open=(tf=="1h"))')
        source = source.replace('raw={tf:fetch(sym,tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000)) for tf in ("1h","30m","4h","1d")}',
'''raw={tf:fetch(sym,tf,int(fetch_start.timestamp()*1000),
                          int((end+pd.Timedelta(hours=73)).timestamp()*1000) if tf=="1h" else int(end.timestamp()*1000),
                          include_boundary_open=(tf=="1h"),
                          signal_boundary_ms=int(end.timestamp()*1000) if tf=="1h" else None)
                  for tf in ("1h","30m","4h","1d")}''')
        source = source.replace('                c=h1.iloc[i]; close_time=c.close_time',
                                '                c=h1.iloc[i]; close_time=c.close_time\n                if c.open_time >= end: break', 1)
    return_line = '    return d.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)[["open_time","close_time","open","high","low","close","volume"]]'
    replacement = '''    d=d.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)[["open_time","close_time","open","high","low","close","volume"]]
    _ab_record_input(symbol, tf, d)
    return d'''
    if return_line not in source: raise SystemExit(f"Cannot instrument {label} fetch return")
    source = source.replace(return_line, replacement, 1)
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
    # Store full outputs per sample to compare and inspect after the workflow.
    sample=OUT/f"{phase}-{label}-{ordinal}"
    sample.mkdir(exist_ok=True)
    shutil.copy2(summary_path,sample/"summary.json")
    shutil.copy2(trades_path,sample/"trades.csv")
    return {"label":label,"phase":phase,"ordinal":ordinal,"wall_seconds":round(wall,4),
            "engine_seconds":summary["performance"]["stage_seconds"].get("signal_engine",0),
            "total_instrumented_seconds":summary["performance"]["total_instrumented_seconds"],
            "engine_calls":summary["performance"]["counters"].get("engine_calls"),
            "trade_sha256":hashlib.sha256(trades_path.read_bytes()).hexdigest(),
            "input_manifest_sha256":manifest_sha256,"input_manifest_rows":len(manifest),
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
# Require byte-identical trade rows and equivalent key output metrics across
# all runs. Exact CSV equality is stricter than merely matching trade counts.
baseline=[s for s in samples if s["label"]=="A"]
candidate=[s for s in samples if s["label"]=="B"]
trade_hashes={s["trade_sha256"] for s in samples}
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
summary_hashes={json.dumps(comparable(s),sort_keys=True,default=str) for s in samples}
if len(trade_hashes)!=1 or len(summary_hashes)!=1:
    (OUT/"mismatch.json").write_text(json.dumps({
        "trade_hashes":[s["trade_sha256"] for s in samples],
        "summaries":[{"label":s["label"],"phase":s["phase"],"ordinal":s["ordinal"],
                      "summary":comparable(s)} for s in samples]},indent=2,default=str))
    raise SystemExit("OUTPUT MISMATCH: do not merge; see mismatch.json")
def stats(rows,key):
    values=[float(r[key]) for r in rows]
    return {"samples":values,"median":round(median(values),4),
            "min":round(min(values),4),"max":round(max(values),4),
            "range":round(max(values)-min(values),4)}
report={
 "status":"PASS_OUTPUTS_IDENTICAL",
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
 "trade_sha256":next(iter(trade_hashes)),
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
print("A/B benchmark: PASS (identical outputs)",flush=True)
