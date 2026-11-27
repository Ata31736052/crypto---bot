#!/usr/bin/env python3
"""Approximate earliest available 1h kline for Run #160 REVERSAL candidate symbols."""
import csv, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE=os.getenv("BINANCE_BASE_URL","https://data-api.binance.vision").rstrip("/")
START=datetime(2026,5,18,6,0,tzinfo=timezone.utc)
SYMBOL_FILE=Path("diagnostics/run160_candidate_symbols.txt")
OUT=Path("universe-snapshots"); OUT.mkdir(exist_ok=True)
rows=[]
for symbol in [x.strip() for x in SYMBOL_FILE.read_text().splitlines() if x.strip()]:
    item={"symbol":symbol,"first_available_1h_open_utc":None,"status":"unknown","note":"Earliest retrievable hourly kline; not an exact listing timestamp"}
    try:
        response=requests.get(f"{BASE}/api/v3/klines",
            params={"symbol":symbol,"interval":"1h","startTime":0,"limit":1},timeout=30)
        if response.status_code==200:
            data=response.json()
            if isinstance(data,list) and data:
                item["first_available_1h_open_utc"]=datetime.fromtimestamp(int(data[0][0])/1000,timezone.utc).isoformat()
                item["status"]="first_kline_found"
                item["available_before_run160_start"]=int(data[0][0]) < int(START.timestamp()*1000)
            else:
                item["status"]="no_kline_returned"
        elif response.status_code in (400,404):
            item["status"]="symbol_unavailable_or_invalid_now"
            item["http_status"]=response.status_code
        else:
            item["status"]="http_error"
            item["http_status"]=response.status_code
            item["response_excerpt"]=response.text[:250]
    except Exception as exc:
        item["status"]="request_error"
        item["error"]=str(exc)[:250]
    rows.append(item)
    time.sleep(0.12)

stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
payload={"schema_version":1,"captured_at_utc":datetime.now(timezone.utc).isoformat(),
         "run160_window_start_utc":START.isoformat(),"symbol_count":len(rows),
         "method":"Binance Spot public klines endpoint, interval=1h, startTime=0, limit=1",
         "warning":"First retrievable candle is only an approximate history boundary. It does not prove exact listing time or continuous TRADING status.",
         "results":rows}
(OUT/f"run160-first-kline-{stamp}.json").write_text(json.dumps(payload,indent=2)+"\n")
with (OUT/f"run160-first-kline-{stamp}.csv").open("w",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=sorted({k for row in rows for k in row}))
    writer.writeheader(); writer.writerows(rows)
print(json.dumps({"symbol_count":len(rows),"found":sum(x["status"]=="first_kline_found" for x in rows),
 "before_window":sum(x.get("available_before_run160_start") is True for x in rows),
 "errors":sum(x["status"] not in ("first_kline_found","no_kline_returned","symbol_unavailable_or_invalid_now") for x in rows)},indent=2))
