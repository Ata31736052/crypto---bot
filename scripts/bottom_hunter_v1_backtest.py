#!/usr/bin/env python3
"""No-lookahead 180d shared-capital replay for isolated Bottom Hunter v1."""
import csv, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bottom_hunter_v1.core import find_signal, find_early_warning

BASE = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision")
SYMBOLS = [x.strip().upper() for x in os.getenv("BH_BACKTEST_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,TRXUSDT").split(",") if x.strip()]
DAYS = int(os.getenv("BH_BACKTEST_DAYS", "180"))
INITIAL = float(os.getenv("BH_INITIAL_USDT", "1000"))
RISK_FRACTION = float(os.getenv("BH_RISK_FRACTION", "0.01"))
MAX_NOTIONAL = float(os.getenv("BH_MAX_NOTIONAL_USDT", "1000"))
FEE_BPS = float(os.getenv("BH_FEE_BPS", "10"))
SLIP_BPS = float(os.getenv("BH_SLIPPAGE_BPS", "5"))
OUT = Path("bottom-hunter-results")
OUT.mkdir(exist_ok=True)
S = requests.Session()

def fetch(symbol, start_ms, end_ms):
    rows, cursor = [], start_ms
    while cursor < end_ms:
        r = S.get(BASE + "/api/v3/klines", params={"symbol": symbol, "interval":"1h", "startTime":cursor, "endTime":end_ms, "limit":1000}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch: break
        rows.extend(batch)
        next_cursor = int(batch[-1][0]) + 3600000
        if next_cursor <= cursor: raise RuntimeError("Binance pagination did not advance")
        cursor = next_cursor
        if len(batch) < 1000: break
        time.sleep(0.08)
    # Keep only candles closed at the fixed end timestamp.
    return [{"open_time":int(x[0]),"close_time":int(x[6]),"open":float(x[1]),"high":float(x[2]),"low":float(x[3]),"close":float(x[4]),"volume":float(x[5])} for x in rows if int(x[6]) < end_ms]

def main():
    end = int(datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).timestamp()*1000)
    start = end - DAYS*24*3600000
    warm = start - 35*24*3600000
    series = {}
    for symbol in SYMBOLS:
        bars = fetch(symbol, warm, end)
        if len(bars) < 30: raise RuntimeError(f"Insufficient candles for {symbol}: {len(bars)}")
        series[symbol] = bars
    # Generate events only from bars available at that close. The following bar's open is the earliest execution.
    events, warnings = [], []
    for symbol, bars in series.items():
        for i, bar in enumerate(bars):
            if bar["open_time"] < start or bar["close_time"] >= end or i+1 >= len(bars): continue
            history = bars[:i+1]
            w = find_early_warning(history, symbol)
            if w:
                warnings.append({"symbol":symbol,"signal_time":bar["close_time"],"decline_pct":w["decline_pct"]})
            sig = find_signal(history, symbol)
            if sig:
                events.append({"symbol":symbol,"signal_time":bar["close_time"],"entry_time":bars[i+1]["open_time"],"entry_bar_index":i+1,"bars":bars,"signal":sig})
    events.sort(key=lambda e:(e["entry_time"],e["symbol"]))
    equity, peak, max_dd = INITIAL, INITIAL, 0.0
    available_time = 0
    trades = []
    for e in events:
        if e["entry_time"] < available_time: continue
        bars, sig, idx = e["bars"], e["signal"], e["entry_bar_index"]
        raw_entry = bars[idx]["open"]
        entry = raw_entry*(1+SLIP_BPS/10000)
        stop = sig["stop_loss"]
        risk_per_unit = entry-stop
        if risk_per_unit <= 0: continue
        qty = min(equity*RISK_FRACTION/risk_per_unit, MAX_NOTIONAL/entry)
        if qty <= 0: continue
        tp1, tp2 = sig["take_profit_1"], sig["take_profit_2"]
        remaining, realized, exit_time, reason = qty, 0.0, None, "TIME_END"
        tp1_done = False
        for j in range(idx, len(bars)):
            b = bars[j]
            if b["open_time"] >= end: break
            # Conservative gap-aware fills. If stop and target are both touched in a bar, stop wins.
            if b["open"] <= stop:
                px = b["open"]*(1-SLIP_BPS/10000); realized += remaining*(px-entry); exit_time=b["open_time"]; reason="STOP_GAP"; break
            if b["open"] >= tp2:
                px = b["open"]*(1-SLIP_BPS/10000); realized += remaining*(px-entry); exit_time=b["open_time"]; reason="TP2_GAP"; break
            if b["low"] <= stop:
                px = stop*(1-SLIP_BPS/10000); realized += remaining*(px-entry); exit_time=b["close_time"]; reason="STOP"; break
            # Take TP1 only once. If both targets are reached in the same candle,
            # realize half at TP1 and the remainder at TP2 (unless stop was touched).
            if not tp1_done and b["high"] >= tp1 and remaining > 0:
                partial = remaining*0.5
                px = tp1*(1-SLIP_BPS/10000); realized += partial*(px-entry); remaining -= partial
                tp1_done = True
            if b["high"] >= tp2 and remaining > 0:
                px = tp2*(1-SLIP_BPS/10000); realized += remaining*(px-entry); remaining = 0.0
                exit_time=b["close_time"]; reason="TP2"; break
        if exit_time is None:
            last = next((b for b in reversed(bars[idx:]) if b["open_time"] < end), None)
            if last is None: continue
            px = last["close"]*(1-SLIP_BPS/10000)
            realized += remaining*(px-entry); exit_time=last["close_time"]
        # Fees on both entry and all exit notional, conservatively charge exit on gross exit quantity.
        entry_fee = qty*entry*FEE_BPS/10000
        # approximate exit notional from realized gross PnL plus cost basis of sold units
        sold_qty = qty
        exit_notional = max(0.0, sold_qty*entry + realized)
        fees = entry_fee + exit_notional*FEE_BPS/10000
        net = realized-fees
        equity += net
        peak = max(peak,equity)
        max_dd = max(max_dd,(peak-equity)/peak if peak else 0.0)
        available_time = exit_time
        trades.append({"symbol":e["symbol"],"signal_time":e["signal_time"],"entry_time":e["entry_time"],"exit_time":exit_time,"entry":round(entry,10),"stop":round(stop,10),"tp1":round(tp1,10),"tp2":round(tp2,10),"net_pnl":round(net,6),"equity_after":round(equity,6),"exit_reason":reason,"fee_bps":FEE_BPS,"slippage_bps":SLIP_BPS})
    net = equity-INITIAL
    wins = sum(1 for t in trades if t["net_pnl"]>0)
    summary = {"status":"research_only","period_days":DAYS,"start_utc":datetime.fromtimestamp(start/1000,timezone.utc).isoformat(),"end_utc":datetime.fromtimestamp(end/1000,timezone.utc).isoformat(),"symbols":SYMBOLS,"initial_usdt":INITIAL,"final_usdt":round(equity,6),"net_pnl_usdt":round(net,6),"return_pct":round(net/INITIAL*100,4),"max_drawdown_pct":round(max_dd*100,4),"trades":len(trades),"wins":wins,"win_rate_pct":round(wins/len(trades)*100,3) if trades else 0,"watch_warnings":len(warnings),"skipped_overlapping_signals":len(events)-len(trades),"fee_bps_each_side":FEE_BPS,"slippage_bps_each_side":SLIP_BPS,"risk_fraction":RISK_FRACTION,"max_notional_usdt":MAX_NOTIONAL,"caveats":["Historical replay is not proof of future performance.","Single shared position at a time; conservative stop-first ordering when stop and targets are touched in one candle.","TP1 takes half off; stop is not moved to breakeven.","No live orders are placed."]}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2))
    for name, rows in (("trades.csv",trades),("warnings.csv",warnings)):
        with (OUT/name).open("w",newline="") as f:
            if rows:
                writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps(summary,indent=2))
    if not trades: raise SystemExit("NO_TRADES: no performance conclusion can be drawn")

if __name__ == "__main__": main()
