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

def signal_diagnostics(df, side):
    """Capture signal-time location/momentum fields to diagnose late entries."""
    if df is None or len(df) < 22:
        return {}
    row=df.iloc[-1]
    close=float(row.get("close",0) or 0); atr=float(row.get("atr",0) or 0)
    if close <= 0 or atr <= 0:
        return {}
    prior=df.iloc[-21:-1]
    highs=pd.to_numeric(prior["high"],errors="coerce")
    lows=pd.to_numeric(prior["low"],errors="coerce")
    resistance=highs[highs>close].min() if (highs>close).any() else float("nan")
    support=lows[lows<close].max() if (lows<close).any() else float("nan")
    room=(float(resistance)-close)/atr if side=="BUY" and pd.notna(resistance) else ((close-float(support))/atr if side=="SELL" and pd.notna(support) else float("nan"))
    out={"signal_close":close,"signal_atr":atr,"atr_pct":float(row.get("atr_percent",0) or 0),
         "rsi":float(row.get("rsi",0) or 0),"adx":float(row.get("adx",0) or 0),
         "volume_ratio":float(row.get("volume_ratio",0) or 0),
         "ema21_extension_atr":((close-float(row.get("ema21",close) or close))/atr)*(1 if side=="BUY" else -1),
         "room_to_obstacle_atr":room}
    for n in (6,12,24):
        past=float(df.iloc[-1-n]["close"]) if len(df)>n else 0
        out[f"directional_move_{n}h_pct"]=((close/past-1)*100*(1 if side=="BUY" else -1)) if past>0 else float("nan")
    hi=float(highs.max()) if highs.notna().any() else close
    lo=float(lows.min()) if lows.notna().any() else close
    out["range_position_20"]=((close-lo)/(hi-lo)) if hi>lo else 0.5
    # Backtest-only location diagnostic. Keep it local so the replay can
    # compare candidate engine versions even when main.py has no public guard.
    prior = df.iloc[-21:-1]
    if side == "BUY":
        levels = pd.to_numeric(prior["high"], errors="coerce")
        levels = levels[levels > close]
        if levels.empty:
            allowed, reason = True, "ENTRY_LOCATION_LEVEL_CLEARED_RESISTANCE"
        else:
            room_atr = (float(levels.min()) - close) / atr
            allowed = room_atr >= 0.80
            reason = f"ENTRY_LOCATION_ROOM_{room_atr:.2f}_ATR"
    else:
        levels = pd.to_numeric(prior["low"], errors="coerce")
        levels = levels[levels < close]
        if levels.empty:
            allowed, reason = True, "ENTRY_LOCATION_LEVEL_CLEARED_SUPPORT"
        else:
            room_atr = (close - float(levels.max())) / atr
            allowed = room_atr >= 0.80
            reason = f"ENTRY_LOCATION_ROOM_{room_atr:.2f}_ATR"
    out["entry_guard_allowed"] = bool(allowed)
    out["entry_guard_reason"] = reason
    return out


def simulate(symbol,side,signal_time,entry_i,h1,atr,score,strength,signal_obj=None):
    row=h1.iloc[entry_i]; entry=float(row.open)
    if entry<=0 or atr<=0:return None,entry_i
    # Reuse the production engine's validated stop distance, re-anchored to
    # the next candle's executable open. This preserves structural Bottom Hunter
    # stops and the 4H/Daily stop multiplier instead of forcing every engine
    # to use the generic 1H ATR stop.
    engine_entry=float((signal_obj or {}).get("entry",0) or (signal_obj or {}).get("price",0) or 0)
    engine_stop=float((signal_obj or {}).get("stop_loss",0) or 0)
    risk=abs(engine_entry-engine_stop) if engine_entry>0 and engine_stop>0 else 0.0
    if risk<=0:
        risk=atr*float(getattr(main,"SL_ATR_MULTIPLIER",1.5))
    rr1=float(getattr(main,"TP1_RR",1.8)); rr2=float(getattr(main,"TP2_RR",2.4))
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

def historical_btc_regime(frames, decision_time):
    """Rebuild the engine's combined BTC 1H + Daily regime using only closed candles."""
    latest = {}
    for tf in ("1h", "1d"):
        df = frames.get(tf)
        if df is None or df.empty:
            return None
        closed = df[df["close_time"] <= decision_time]
        if closed.empty:
            return None
        latest[tf] = main._btc_regime_from_row(closed.iloc[-1])
    h, d = latest["1h"], latest["1d"]
    if h["bullish"] and d["bullish"]:
        combined = "BULLISH"
    elif h["bearish"] and d["bearish"]:
        combined = "BEARISH"
    elif h["bearish"] and d["bullish"]:
        combined = "MIXED_BEARISH_1H"
    elif h["bullish"] and d["bearish"]:
        combined = "MIXED_BULLISH_1H"
    else:
        combined = "NEUTRAL"
    return {"combined": combined, "combined_score": h["score"] + d["score"], "1h": h, "daily": d}

def run():
    end=pd.Timestamp.now(tz="UTC").floor("h"); start=end-pd.Timedelta(days=DAYS); fetch_start=start-pd.Timedelta(days=30)
    trades=[]; errors=[]; diagnostics={"evaluated":0,"no_signal":0,"signals_before_execution":0,"signals_rejected_anti_chase":0,"first_no_signal_reasons":[]}
    print(f"PERIOD {start} -> {end}; symbols={SYMBOLS}; fee/side={FEE_BPS}bps; slippage/side={SLIPPAGE_BPS}bps",flush=True)
    # Fetch BTC context once and rebuild it at each historical decision instant.
    try:
        btc_raw={tf:fetch("BTCUSDT",tf,int(fetch_start.timestamp()*1000),int(end.timestamp()*1000)) for tf in ("1h","1d")}
        btc_frames={tf:prepare(df) for tf,df in btc_raw.items()}
        if btc_frames["1h"].empty or btc_frames["1d"].empty:
            raise RuntimeError("BTC historical context unavailable")
        print("BTC historical context loaded",flush=True)
    except Exception as exc:
        errors.append({"symbol":"BTCUSDT","error":f"BTC context: {exc}"})
        btc_frames={"1h":pd.DataFrame(),"1d":pd.DataFrame()}
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
                btc_regime=historical_btc_regime(btc_frames,close_time)
                if btc_regime is None:
                    errors.append({"symbol":sym,"time":str(close_time),"error":"BTC historical regime unavailable"})
                    continue
                diagnostics["evaluated"] += 1
                # Run the same production candidate pipeline (Trend, Bottom Hunter,
                # Breakout, plus enabled higher-timeframe candidates) without live
                # API calls. Only the price/market-data providers are replaced.
                original_prepare=main.prepare_symbol_data
                original_live_price=main.get_live_price
                try:
                    main.prepare_symbol_data=lambda _symbol, _data=data: _data
                    current_price=float(data["1h"].iloc[-1]["close"])
                    current_close_time=str(data["1h"].iloc[-1]["close_time"])
                    main.get_live_price=lambda _symbol, _price=current_price, _time=current_close_time: {
                        "price":_price,"fetched_at":_time,"request_latency_seconds":0.0,"source":"historical closed candle"
                    }
                    scan=main.analyze_one_symbol(sym,btc_regime)
                except Exception as exc:
                    errors.append({"symbol":sym,"time":str(close_time),"error":f"production pipeline: {exc}"})
                    continue
                finally:
                    main.prepare_symbol_data=original_prepare
                    main.get_live_price=original_live_price
                selected=scan.get("signal") if isinstance(scan,dict) else None
                higher=scan.get("higher_signals",[]) if isinstance(scan,dict) else []
                candidates=[x for x in [selected]+(higher if isinstance(higher,list) else []) if isinstance(x,dict) and str(x.get("signal","")).upper() in ("BUY","SELL")]
                if not candidates:
                    diagnostics["no_signal"] += 1
                    trace=(scan.get("symbol_trace",{}) if isinstance(scan,dict) else {}) or {}
                    if len(diagnostics["first_no_signal_reasons"]) < 12:
                        diagnostics["first_no_signal_reasons"].append({"symbol":sym,"time":str(close_time),"first_rejection":trace.get("first_rejection"),"final_rejection":trace.get("final_rejection"),"error":scan.get("error") if isinstance(scan,dict) else "invalid scan result"})
                    continue
                # The live scan can surface multiple qualified timeframes; because
                # this replay permits one position per symbol, select the strongest
                # qualified candidate at that decision time.
                result=max(candidates,key=lambda x:(float(x.get("professional_quality_score",0) or 0),float(x.get("score",0) or 0),1 if x.get("strength")=="STRONG" else 0))
                side=str(result.get("signal","NO_SIGNAL")).upper()
                diagnostics["signals_before_execution"] += 1
                # EXPERIMENTAL backtest-only anti-chase test. This is intentionally
                # not wired into main.py: compare current baseline against rejecting
                # BUY signals already >1.50 ATR above EMA21, including Bottom Hunter.
                location_diag = signal_diagnostics(data["1h"],side)
                ema21_extension = float(location_diag.get("ema21_extension_atr",0) or 0)
                if side == "BUY" and ema21_extension > 1.50:
                    diagnostics["signals_rejected_anti_chase"] += 1
                    print(f"ANTI_CHASE_REJECT {sym} {side} {c.open_time} engine={result.get('engine',result.get('signal_mode','UNKNOWN'))} ema21_extension={ema21_extension:.2f} ATR",flush=True)
                    continue
                trade,exit_i=simulate(sym,side,c.open_time,i+1,h1,float(c.get("atr",0) or 0),result.get("score",0),result.get("strength",""),result)
                if trade:
                    trade.update(location_diag)
                    trade["engine"]=result.get("engine",result.get("signal_mode","UNKNOWN"))
                    trade["signal_mode"]=result.get("signal_mode","UNKNOWN")
                    trade["btc_regime"]=btc_regime.get("combined","UNKNOWN")
                    trades.append(trade); last_exit=exit_i
                    print(f"TRADE {sym} {side} {trade['signal_time']} engine={trade['engine']} net={trade['net_pct']}% {trade['exit_reason']}",flush=True)
        except Exception as exc:
            errors.append({"symbol":sym,"error":str(exc)}); print("ERROR",sym,exc,flush=True)
    columns=["symbol","side","signal_time","entry_time","entry","stop_loss","tp1","tp2","exit_time","exit","exit_reason","gross_pct","cost_pct","net_pct","bars_held","score","strength","btc_regime","engine","signal_mode","signal_close","signal_atr","atr_pct","rsi","adx","volume_ratio","ema21_extension_atr","room_to_obstacle_atr","directional_move_6h_pct","directional_move_12h_pct","directional_move_24h_pct","range_position_20","entry_guard_allowed","entry_guard_reason"]
    pd.DataFrame(trades,columns=columns).to_csv(OUT/"trades.csv",index=False)
    vals=[float(t["net_pct"]) for t in trades]
    summary={"status":"COMPLETED_WITH_ERRORS" if errors else "COMPLETED","period_start":str(start),"period_end":str(end),"days":DAYS,"symbols":SYMBOLS,"trade_count":len(trades),"win_rate_pct":round(sum(v>0 for v in vals)/len(vals)*100,2) if vals else None,"gross_return_sum_pct":round(sum(t["gross_pct"] for t in trades),4),"net_return_sum_pct":round(sum(vals),4),"average_net_trade_pct":round(sum(vals)/len(vals),4) if vals else None,"profit_factor":round(sum(v for v in vals if v>0)/abs(sum(v for v in vals if v<0)),3) if any(v<0 for v in vals) else None,"exit_reasons":{k:sum(t["exit_reason"]==k for t in trades) for k in sorted({t["exit_reason"] for t in trades})},"assumptions":{"entry":"next 1H candle open after signal candle closes","stop":"engine SL_ATR_MULTIPLIER; fallback 1.5 ATR","targets":"engine TP1_RR/TP2_RR; first touched target exits full position","same_candle_conflict":"SL-first conservative","costs":"fee and slippage on both entry and exit","overlap":"one position per symbol at a time","btc_regime":"Historical BTC 1H and Daily regime rebuilt from closed candles at each decision time","experimental_filter":"Reject BUY signal when close is >1.50 ATR above EMA21; backtest-only hypothesis, not live-engine change","returns":"sum of trade percentages, not a compounded portfolio equity curve"},"engine_breakdown":{k:{"trades":sum(str(t.get("engine","UNKNOWN"))==k for t in trades),"net_return_sum_pct":round(sum(float(t["net_pct"]) for t in trades if str(t.get("engine","UNKNOWN"))==k),4)} for k in sorted({str(t.get("engine","UNKNOWN")) for t in trades})},"diagnostics":diagnostics,"errors":errors}
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8"); print(json.dumps(summary,indent=2),flush=True)
    if not trades: raise SystemExit("No trades produced; do not infer profitability.")

if __name__=="__main__": run()
