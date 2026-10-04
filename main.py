import importlib.util
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('bot', '/mnt/data/main_v61.py')
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

N = 80

def frame(close=100.0, ema9=101.0, ema21=99.0, ema50=97.0, ema200=89.3,
          adx=30.0, plus=30.0, minus=15.0, rsi=60.0, rsi_prev=58.0,
          vol=2.0, atrp=2.5, dist21=3.0, vwap=98.0, obv=1.0,
          bb_width=6.0, bb_pos=0.70, macd=1.0, macd_signal=0.5,
          hist=0.5, hist_prev=0.4, bearish=0.0, atr=2.0):
    d = {
        'close': np.full(N, close), 'ema9': np.full(N, ema9), 'ema21': np.full(N, ema21),
        'ema50': np.full(N, ema50), 'ema200': np.full(N, ema200), 'adx': np.full(N, adx),
        'plus_di': np.full(N, plus), 'minus_di': np.full(N, minus), 'rsi': np.full(N, rsi),
        'rsi_prev': np.full(N, rsi_prev), 'volume_ratio': np.full(N, vol),
        'atr_percent': np.full(N, atrp), 'distance_ema21': np.full(N, dist21),
        'rolling_vwap': np.full(N, vwap), 'obv_slope': np.full(N, obv),
        'bb_width_pct': np.full(N, bb_width), 'bb_position': np.full(N, bb_pos),
        'macd': np.full(N, macd), 'macd_signal': np.full(N, macd_signal),
        'macd_hist': np.full(N, hist), 'macd_hist_prev': np.full(N, hist_prev),
        'bearish_candle': np.full(N, bearish), 'atr': np.full(N, atr),
        'high': np.full(N, close + 4), 'low': np.full(N, close - 4),
        'open_time': np.arange(N),
    }
    return pd.DataFrame(d)

base1 = frame(close=100, ema9=101, ema21=99, ema200=89.27, adx=30.8,
              plus=32, minus=14, rsi=66.7, vol=2.11, atrp=2.47,
              dist21=4.49, vwap=98, bb_pos=.75)
base30 = frame(close=100, ema9=101, ema21=99, ema200=90, adx=22, plus=25, minus=15,
               rsi=60, vol=1.5, atrp=2, dist21=1.0, vwap=98, bb_pos=.7)
base4 = frame(close=100, ema9=101, ema21=99, ema200=90, adx=28, plus=30, minus=15,
              rsi=60, vol=2, atrp=3, dist21=2, vwap=98, bb_pos=.7)
baseD = frame(close=100, ema9=101, ema21=99, ema200=90, adx=25, plus=28, minus=15,
              rsi=58, vol=1.5, atrp=3, dist21=2, vwap=98, bb_pos=.7)
data = {'1h':base1, '30m':base30, '4h':base4, '1d':baseD}
bot.score_30m_confirmation = lambda df, side: {'confirmed': True, 'confirmations': 5}

sig = {'signal':'BUY','signal_mode':'TREND','signal_timeframe':'1h','score':96,'rr_tp1':1.60,'rr_tp2':2.80,'reasons':[]}
ok, reasons, q = bot.professional_signal_quality_gate(sig, data, {'combined':'NEUTRAL'})
assert ok, reasons
assert sig['professional_quality_grade'] == 'A+', sig
print('1) MUBARAK-like strong BUY: PASS', sig['professional_quality_grade'], sig['professional_quality_points'])

late4 = frame(close=100, ema9=101, ema21=99, ema200=84.99, adx=30.4, plus=30, minus=14,
              rsi=56.3, vol=2.30, atrp=3.82, dist21=3.0, vwap=98, bb_pos=.65)
sig2 = {'signal':'BUY','signal_mode':'4H_SIGNAL','signal_timeframe':'4h','score':86,'rr_tp1':1.60,'rr_tp2':2.80,'reasons':[]}
ok, reasons, q = bot.professional_signal_quality_gate(sig2, {'1h':base1,'30m':base30,'4h':late4,'1d':baseD}, {'combined':'NEUTRAL'})
assert not ok and any('EMA200' in r for r in reasons), reasons
print('2) KITE-like overextended 4H: PASS (rejected)', reasons)

lowvol = base1.copy(); lowvol.loc[lowvol.index[-1], 'volume_ratio'] = 0.80
sig3 = {'signal':'BUY','signal_mode':'TREND','signal_timeframe':'1h','score':96,'rr_tp1':1.60,'rr_tp2':2.80,'reasons':[]}
ok, reasons, q = bot.professional_signal_quality_gate(sig3, {'1h':lowvol,'30m':base30,'4h':base4,'1d':baseD}, {'combined':'NEUTRAL'})
assert not ok and any('volume below professional minimum' in r for r in reasons), reasons
print('3) Weak-volume high-score BUY: PASS (rejected)', reasons)

sell = frame(close=100, ema9=98, ema21=99, ema200=110, adx=23, plus=14, minus=30,
             rsi=50, rsi_prev=52, vol=1.25, atrp=2.5, dist21=1.0, vwap=102,
             obv=-1, bb_pos=.30, macd=-1, macd_signal=-.5, hist=-.5, hist_prev=-.4, bearish=1)
sig4 = {'signal':'SELL','signal_mode':'TREND','signal_timeframe':'1h','score':87,'rr_tp1':1.60,'rr_tp2':2.80,'reasons':[]}
ok, reasons, q = bot.professional_signal_quality_gate(sig4, {'1h':sell,'30m':base30,'4h':sell,'1d':sell}, {'combined':'NEUTRAL'})
assert not ok and any('score' in r for r in reasons), reasons
print('4) SELL below v61 threshold: PASS (rejected)', reasons)

print('V61 ROOT BEHAVIORAL TESTS: PASS')
