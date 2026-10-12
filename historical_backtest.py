#!/usr/bin/env python3
"""Closed-candle historical replay of the repository signal engine. No orders or Telegram."""
import json, os, time
from pathlib import Path
import pandas as pd
import requests
import main

BASE = os.getenv("BINANCE_BASE_URL", "https://data-api.binance.vision")
SYMBOLS = [s.strip().upper().replace("/", "").replace("-", "") for s in (os.getenv("BACKTEST_SYMBOLS") or "ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT,LINKUSDT").split(",") if s.strip()]
DAYS = max(30, min(365, int((os.getenv("BACKTEST_DAYS") or "180"))))
FEE_BPS = float((os.getenv("BACKTEST_FEE_BPS") or "10"))
SLIPPAGE_BPS = float((os.getenv("BACKTEST_SLIPPAGE_BPS") or "5"))
OUT = Path("backtest-results"); OUT.mkdir(exist_ok=True)
MS = {"1h":3600000,"30m":1800000,"4h":14400000,"1d":86400000}
SESSION = requests.Session()

def fetch(symbol, tf, start_ms, end_ms):
    rows=[]; cursor=start_ms
    while cursor < end_ms:
        r=SESSION.get(f"{BASE}/api/v3/klines",params={"symbol":symbol,"interval":tf,"startTime":cursor,"endTime":end_ms,"limit":1000},timeout=30)
        r.raise_for_status(); batch=r.json()
        if not isinstance(batch,list): raise RuntimeError(f"Bad Binance response: {symbol} {tf}")
        if not batch: break
        rows.extend(batch); nxt=int(batch[-1][0])+MS[tf]
        if nxt<=cursor: raise RuntimeError("Pagination stalled")
        cursor=nxt
        if len(batch)<1000: break
        time.sleep(.08)
    if not rows: return pd.DataFrame()
    d=pd.DataFrame(rows,columns=["open_time","open","high","low","close","volume","close_time","qv","trades","tb","tq","ignore"])
    d["open_time"]=pd.to_datetime(d.open_time,unit="ms",utc=True); d["close_time"]=pd.to_datetime(d.close_time,unit="ms",utc=True)
    for c in ("open","high","low","close","volume"): d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d[d.close_time < pd.Timestamp.now(tz="UTC")].dropna(subset=["open","high","low","close","volume"])
    return d.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)[["open_time","close_time","open","high","low","close","volume"]]

def prepare(d):
    if d.empty: return d
    x=main.add_indicators(d.copy())
    return x.sort_values("open_time").reset_index(drop=True) if x is not None and not x.empty else pd.DataFrame()

def simulate(symbol,side,signal_time,entry_i,h1,atr,score,strength):
    row=h1.iloc[entry_i]; entry=float(row.open)
    if entry<=0 or atr<=0:return None,entry_i
    risk=atr*float(getattr(main,"SL_ATR_MULTIPLIER",1.5)); rr1=float(getattr(main,"TP1_RR",1.8)); rr2=float(getattr(main,"TP2_RR",2.4))
    if side=="BUY": sl,tp1,tp2=entry-risk,entry+risk*rr1,entry+risk*rr2
    else: sl,tp1,tp2=entry+risk,entry-risk*rr1,entry-risk*rr2
    end_i=min(len(h1)-1,entry_i+72); exitp=float(h1.iloc[end_i].close); reason="TIME_EXIT_72H"; xi=end_i
    # Conservative OHLC ambiguity policy: stop loss wins if multiple levels touched in one candle.
    for j in range(entry_i,end_i+1):
        c=h1.iloc[j]; hi,lo=float(c.high),float(c.low)
        slhit=(lo<=sl if side=="BUY" else hi>=sl)
        t2=(hi>=tp2 if side=="BUY" else lo<=tp2)
        t1=(hi>=tp1 if side=="BUY" else lo<=tp1)
        if slhit: exitp,reason,xi=sl,"SL",j; break
        if t2: exitp,reason,xi=tp2,"TP2",j; break
        if t1: exitp,reason,xi=tp1,"TP1",j; break
    gross=((exitp-entry)/entry*100) if side=="BUY" else ((entry-exitp)/entry*100)
    costs=2*(FEE_BPS+SLIPPAGE_BPS)/100
    return {"symbol":symbol,"side":side,"signal_time":str(signal_time),"entry_time":str(row.open_time),"entry":entry,"stop_loss":sl,"tp1":tp1,"tp2":tp2,"exit_time":str(h1.iloc[xi].open_time),"exit":exitp,"exit_reason":reason,"gross_pct":round(gross,4),"cost_pct":round(costs,4),"net_pct":round(gross-costs,4),"bars_held":xi-entry_i,"score":score,"strength":strength},xi

def run():
    end=pd.Timestamp.now(tz="UTC").floor("h"); start=end-pd.Timedelta(days=DAYS); fetch_start=start-pd.Timedelta(days=30)
    trades=[]; errors=[]
    print(f"PERIOD {start} -> {end}; symbols={SYMBOLS}; fee/side={FEE_BPS}bps; slippage/side={SLIPPAGE_BPS}bps",flush=True)
    for sym in SYMBOLS:
        try:
            print("FETCH",sym,flush=True)
            raw={tf:fetch(sym,tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000)) for tf in ("1h","30m","4h","1d")}
            if len(raw["1h"])<250 or len(raw["30m"])<50: raise RuntimeError("Insufficient historical candles")
            frames={tf:prepare(d) for tf,d in raw.items()}; h1=frames["1h"]
            idx=max(220,int(h1.open_time.searchsorted(start))); last_exit=idx-1
            for i in range(idx,len(h1)-1):
                c=h1.iloc[i]; close_time=c.close_time
                if close_time<start or i<=last_exit: continue
                data={}
                for tf,df in frames.items():
                    data[tf]=df[df.close_time<=close_time].copy() if not df.empty else None
                if len(data["1h"])<50 or len(data["30m"])<30: continue
                try: result=main.evaluate_final_signal(sym,data,btc_regime=None)
                except Exception as exc:
                    errors.append({"symbol":sym,"time":str(close_time),"error":str(exc)}); continue
                side=str(result.get("signal","NO_SIGNAL")).upper()
                if side not in ("BUY","SELL"): continue
                trade,exit_i=simulate(sym,side,c.open_time,i+1,h1,float(c.get("atr",0) or 0),result.get("score",0),result.get("strength",""))
                if trade:
                    trade["btc_regime"]=result.get("btc_regime","UNKNOWN"); trades.append(trade); last_exit=exit_i
                    print(f"TRADE {sym} {side} {trade['signal_time']} net={trade['net_pct']}% {trade['exit_reason']}",flush=True)
        except Exception as exc:
            errors.append({"symbol":sym,"error":str(exc)}); print("ERROR",sym,exc,flush=True)
    columns=["symbol","side","signal_time","entry_time","entry","stop_loss","tp1","tp2","exit_time","exit","exit_reason","gross_pct","cost_pct","net_pct","bars_held","score","strength","btc_regime"]
    pd.DataFrame(trades,columns=columns).to_csv(OUT/"trades.csv",index=False)
    vals=[float(t["net_pct"]) for t in trades]
    summary={"status":"COMPLETED_WITH_ERRORS" if errors else "COMPLETED","period_start":str(start),"period_end":str(end),"days":DAYS,"symbols":SYMBOLS,"trade_count":len(trades),"win_rate_pct":round(sum(v>0 for v in vals)/len(vals)*100,2) if vals else None,"gross_return_sum_pct":round(sum(t["gross_pct"] for t in trades),4),"net_return_sum_pct":round(sum(vals),4),"average_net_trade_pct":round(sum(vals)/len(vals),4) if vals else None,"profit_factor":round(sum(v for v in vals if v>0)/abs(sum(v for v in vals if v<0)),3) if any(v<0 for v in vals) else None,"exit_reasons":{k:sum(t["exit_reason"]==k for t in trades) for k in sorted({t["exit_reason"] for t in trades})},"assumptions":{"entry":"next 1H candle open after signal candle closes","stop":"engine SL_ATR_MULTIPLIER; fallback 1.5 ATR","targets":"engine TP1_RR/TP2_RR; first touched target exits full position","same_candle_conflict":"SL-first conservative","costs":"fee and slippage on both entry and exit","overlap":"one position per symbol at a time","btc_regime":"None passed to engine; inspect engine behavior before treating as final decision-grade","returns":"sum of trade percentages, not a compounded portfolio equity curve"},"errors":errors}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8"); print(json.dumps(summary,indent=2),flush=True)
    if not trades: raise SystemExit("No trades produced; do not infer profitability.")

if __name__=="__main__": run()
