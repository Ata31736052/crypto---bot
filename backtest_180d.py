#!/usr/bin/env python3
"""180-day closed-candle BUY-only spot replay using the repository v63.14.28 engine."""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import main

DAYS=int(os.getenv("BACKTEST_DAYS","180")); FEE=float(os.getenv("BACKTEST_FEE_RATE","0.001")); SLIPPAGE=float(os.getenv("BACKTEST_SLIPPAGE_RATE","0.0005"))
SYMBOLS=[x.strip().upper() for x in os.getenv("BACKTEST_SYMBOLS","BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT").split(",") if x.strip()]
MS={"30m":1800000,"1h":3600000,"4h":14400000,"1d":86400000}
OUT=Path("backtest_report"); OUT.mkdir(exist_ok=True)
def ms(t): return int(pd.Timestamp(t).timestamp()*1000)
def fetch(sym,tf,start,end):
    cursor=start; pages=[]
    while cursor<end:
        df=main.get_klines(sym,tf,1000,start_time_ms=cursor,end_time_ms=end)
        if df is None or df.empty: break
        pages.append(df); nxt=ms(df.open_time.iloc[-1])+MS[tf]
        if nxt<=cursor: raise RuntimeError(f"pagination stalled {sym}/{tf}")
        cursor=nxt
        if len(df)<1000: break
        time.sleep(.08)
    if not pages: return None
    d=pd.concat(pages,ignore_index=True).drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    d=d[(d.open_time.map(ms)<end)&(d.close_time<pd.Timestamp.now(tz="UTC"))].copy()
    return main.add_indicators(d)
def asof(d,cut):
    if d is None or d.empty:return None
    # Sorted close_time permits binary search instead of scanning all rows each bar.
    end_idx=int(d["close_time"].searchsorted(cut,side="right"))
    if end_idx<=0:return None
    return d.iloc[max(0,end_idx-260):end_idx].copy()
def btc_regime(r1,rd):
    a=main._btc_regime_from_row(r1); b=main._btc_regime_from_row(rd)
    if a["bullish"] and b["bullish"]: c="BULLISH"
    elif a["bearish"] and b["bearish"]: c="BEARISH"
    elif a["bearish"] and b["bullish"]: c="MIXED_BEARISH_1H"
    elif a["bullish"] and b["bearish"]: c="MIXED_BULLISH_1H"
    else:c="NEUTRAL"
    return {"combined":c,"combined_score":a["score"]+b["score"],"1h":a,"1d":b}
def candidate(sig,entry):
    x=dict(sig); x["price"]=float(entry); lv=main.calculate_trade_levels(x)
    if not lv:return None
    x.update(lv); x.update(entry=lv["entry"],stop_loss=lv["stop_loss"],tp1=lv["tp1"],tp2=lv["tp2"],risk_valid=True)
    return x
def exit_trade(t,future):
    side=t["signal"]; en=t["entry"]; sl=t["stop_loss"]; t1=t["tp1"]; t2=t["tp2"]; qty=float(t.get("position_quantity",0))
    if side != "BUY" or qty<=0:return None
    rem=qty; gross=0.; fees=en*qty*FEE; first=False; reason="TIME_EXIT"; last=en; xt=""
    for _,b in future.iterrows():
        hi,lo=float(b.high),float(b.low); last=float(b.close); xt=str(b.close_time)
        stop_hit=lo<=sl if side=="BUY" else hi>=sl
        hit1=hi>=t1 if side=="BUY" else lo<=t1; hit2=hi>=t2 if side=="BUY" else lo<=t2
        if stop_hit:
            fill=sl*(1-SLIPPAGE); gross+=rem*(fill-en); fees+=rem*fill*FEE; rem=0; reason="SL_AFTER_TP1" if first else "SL"; break
        if not first and hit1:
            part=qty*.5; fill=t1*(1-SLIPPAGE); gross+=part*(fill-en); rem-=part; fees+=part*fill*FEE; first=True
        if first and hit2 and rem>0:
            fill=t2*(1-SLIPPAGE); gross+=rem*(fill-en); fees+=rem*fill*FEE; rem=0; reason="TP2"; break
    if rem>0:
        fill=last*(1-SLIPPAGE); gross+=rem*(fill-en); fees+=rem*fill*FEE
    net=gross-fees; risk=max(float(t.get("actual_risk_usdt",0)),1e-9)
    return {"symbol":t["symbol"],"side":side,"signal_time":t["signal_time"],"entry_time":t["entry_time"],"exit_time":xt,"entry":en,"stop_loss":sl,"tp1":t1,"tp2":t2,"exit_reason":reason,"gross_pnl_usdt":gross,"fees_usdt":fees,"net_pnl_usdt":net,"r_multiple_net":net/risk,"risk_usdt":risk,"position_value_usdt":t.get("position_value_usdt",0),"score":t.get("score",0),"quality_points":t.get("professional_quality_points",0),"grade":t.get("professional_quality_grade","")}
def run_symbol(sym,start,end,btc):
    frames={}
    for tf in ("1h","30m","4h","1d"):
        print(f"FETCH {sym} {tf}",flush=True); frames[tf]=fetch(sym,tf,start-210*MS[tf],end)
        if frames[tf] is None or len(frames[tf])<80:raise RuntimeError(f"insufficient {sym} {tf} data")
    h=frames["1h"]; lo=pd.to_datetime(start,unit="ms",utc=True); hi=pd.to_datetime(end,unit="ms",utc=True)
    replay=h[(h.open_time>=lo)&(h.open_time<hi)].reset_index(drop=True); trades=[]; rejects={}; active=None; last=-10**18
    # Exclude the last 48 bars so every accepted signal has a complete 48-hour outcome window.
    for i in range(max(0,len(replay)-48)):
        if i % 120 == 0: print(f"PROGRESS {sym}: bar {i}/{len(replay)-1} trades={len(trades)}",flush=True)
        bar=replay.iloc[i]; cut=bar.close_time; sm=ms(bar.open_time)
        if active is not None and cut<=active:continue
        if sm-last<6*MS["1h"]:continue
        d={tf:asof(frames[tf],cut) for tf in frames}; b1=asof(btc["1h"],cut); bd=asof(btc["1d"],cut)
        if any(x is None or len(x)<60 for x in list(d.values())+[b1,bd]):continue
        br=btc_regime(b1.iloc[-1],bd.iloc[-1])
        try:sig=main.evaluate_final_signal(symbol=sym,data=d,btc_regime=br)
        except Exception as e:rejects["engine_exception"]=rejects.get("engine_exception",0)+1; print(f"WARN {sym}: {e}",flush=True); continue
        if sig.get("signal") != "BUY":
            if sig.get("signal") == "SELL":
                rejects["spot_sell_signal_not_shortable"]=rejects.get("spot_sell_signal_not_shortable",0)+1
            continue
        nxt=replay.iloc[i+1]
        # Conservative long entry: next-hour open plus modeled slippage.
        c=candidate(sig,float(nxt.open)*(1+SLIPPAGE))
        if c is None:rejects["invalid_levels"]=rejects.get("invalid_levels",0)+1;continue
        ok,reasons,qs=main.professional_signal_quality_gate(c,d,br)
        if not ok:
            for r in reasons[:4]:
                k=str(r).split("(")[0][:90]; rejects[k]=rejects.get(k,0)+1
            continue
        c["professional_filter"]="PASSED"; c["professional_quality_score"]=qs; c["signal_time"]=str(cut); c["entry_time"]=str(nxt.open_time); c["symbol"]=sym
        if not main.final_telegram_quality_gate(c):rejects["final_gate_reject"]=rejects.get("final_gate_reject",0)+1;continue
        t=exit_trade(c,replay.iloc[i+1:min(len(replay),i+49)])
        if t:trades.append(t);last=sm;active=pd.Timestamp(t["exit_time"]) if t["exit_time"] else None
    return trades,rejects,{"symbol":sym,"replay_1h_bars":len(replay),"history_1h_bars":len(h)}
def summarize(ts):
    if not ts:return {"trades":0,"wins":0,"losses":0,"win_rate_pct":0,"gross_pnl_usdt":0,"fees_usdt":0,"net_pnl_usdt":0,"profit_factor":None,"max_drawdown_usdt":0,"expectancy_usdt":0}
    d=pd.DataFrame(ts); w=d[d.net_pnl_usdt>0]; l=d[d.net_pnl_usdt<0]; gp=float(w.net_pnl_usdt.sum()); gl=abs(float(l.net_pnl_usdt.sum())); eq=d.net_pnl_usdt.cumsum(); dd=eq-eq.cummax().clip(lower=0)
    return {"trades":len(d),"wins":len(w),"losses":len(l),"win_rate_pct":round(100*len(w)/len(d),2),"gross_pnl_usdt":round(float(d.gross_pnl_usdt.sum()),4),"fees_usdt":round(float(d.fees_usdt.sum()),4),"net_pnl_usdt":round(float(d.net_pnl_usdt.sum()),4),"profit_factor":round(gp/gl,4) if gl else ("INF" if gp else None),"max_drawdown_usdt":round(float(dd.min()),4),"expectancy_usdt":round(float(d.net_pnl_usdt.mean()),4),"avg_r_net":round(float(d.r_multiple_net.mean()),4)}
def run():
    end=ms(pd.Timestamp.now(tz="UTC").floor("h")); start=end-DAYS*86400000; warm=start-210*86400000
    print(f"BACKTEST days={DAYS}; fee/side={FEE:.3%}; slippage/side={SLIPPAGE:.3%}; BUY-only spot; symbols={SYMBOLS}",flush=True)
    btc={tf:fetch("BTCUSDT",tf,warm,end) for tf in ("1h","1d")}
    if any(x is None or len(x)<100 for x in btc.values()):raise RuntimeError("insufficient BTC regime data")
    alltr=[]; rej={}; cov=[]
    for sym in SYMBOLS:
        ts,rs,cv=run_symbol(sym,start,end,btc);alltr+=ts;cov.append(cv)
        for k,v in rs.items():rej[k]=rej.get(k,0)+v
        print(f"DONE {sym}: trades={len(ts)}",flush=True)
    alltr.sort(key=lambda x:x["entry_time"]); smry=summarize(alltr)
    report={"engine_version":"v63.14.28","method":"repository 1H+30M trend scoring and professional gate; BUY-only spot trades; next-hour-open entry; modeled slippage each side; fees; closed candles; stop-first ambiguous bars; 50/50 TP1/TP2; 48h max hold; 6h cooldown; signals in final 48h excluded so outcomes mature","period_days":DAYS,"start_utc":datetime.fromtimestamp(start/1000,timezone.utc).isoformat(),"end_utc":datetime.fromtimestamp(end/1000,timezone.utc).isoformat(),"symbols":SYMBOLS,"fee_rate_per_side":FEE,"slippage_rate_per_side":SLIPPAGE,"fees_included":True,"summary":smry,"coverage":cov,"rejection_counts":dict(sorted(rej.items(),key=lambda x:-x[1])[:40]),"limitations":["six liquid symbols only, not the full Binance universe","BUY-only spot trades; SELL signals are counted as non-tradable, not simulated as short trades","TREND engine only; Bottom Hunter/Breakout/independent 4H/Daily engines excluded","aggregate PnL sums independent symbol tests and does not enforce a shared 1000-USDT portfolio capital/exposure cap","slippage is a fixed assumption, not a measured order-book simulation","historical simulation is not a guarantee of future returns"]}
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8");pd.DataFrame(alltr).to_csv(OUT/"trades.csv",index=False)
    (OUT/"summary.md").write_text("# ApexSignal historical replay\n\n"+f"- Engine: {report['engine_version']}\n- Days: {DAYS}\n- Symbols: {', '.join(SYMBOLS)}\n- Fee per side: {FEE:.3%}\n- Slippage per side: {SLIPPAGE:.3%}\n- BUY-only spot trades\n- Trades: {smry['trades']}\n- Win rate: {smry['win_rate_pct']}%\n- Net PnL after fees: {smry['net_pnl_usdt']} USDT\n- Profit factor: {smry['profit_factor']}\n- Max trade-equity drawdown: {smry['max_drawdown_usdt']} USDT\n- Expectancy/trade: {smry['expectancy_usdt']} USDT\n\n## Limitations\n"+"\n".join("- "+x for x in report["limitations"])+"\n",encoding="utf-8")
    print(json.dumps(smry),flush=True);print("BACKTEST_REPORT_WRITTEN",flush=True)
if __name__=="__main__":run()
