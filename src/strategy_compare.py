#!/usr/bin/env python3
"""
4策略对比回测
================================================
1. 静态v2     — 非对称DTS v2确认版（我们的策略）
2. 双均线     — MA5/MA20 金叉死叉
3. 多周期共振  — 周线MA20过滤 + 日线MA5触发
4. 海龟CTA    — Donchian通道突破(N=20入/N=10出)
+ BNH 买入持有
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

UPLOADS = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/uploads")
OUTPUT  = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")

# ── v2 params ──
W_FLAT=0.015; W_SAME=0.90; W_REV=0.45
D_FLAT=0.005; COST_BPS=15
UP=1; DOWN=-1; FLAT=0

STATIC_PARAMS = {
    "上证50ETF":  (1.50, 2.50),
    "沪深300ETF": (2.50, 2.50),
    "中证500ETF": (2.50, 2.50),
    "科创50ETF":  (2.50, 1.50),
    "深证100ETF": (3.00, 2.00),
    "创业板ETF":  (4.00, 1.00),
}
ETF_FILES = {
    "上证50ETF":  "510050_上证_50ETF.csv",
    "沪深300ETF": "510300_沪深_300ETF.csv",
    "中证500ETF": "510500_中证_500ETF.csv",
    "科创50ETF":  "588080_科创_50ETF.csv",
    "深证100ETF": "159901_深证_100ETF.csv",
    "创业板ETF":  "159915_创业板_ETF.csv",
}

FULL_START = '2023-04-17'
FULL_END   = '2026-04-15'

# ─────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────
def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close',
                             '最高':'high','最低':'low'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

# ─────────────────────────────────────────────
# v2 signal helpers
# ─────────────────────────────────────────────
def classify(o, h, l, c, thr):
    amp = (h - l) / o
    if amp < thr: return FLAT
    return UP if c >= o else DOWN

def amp_pct(o, h, l):
    return (h - l) / o * 100.0

def seven_rules(dp, dc, ap, ac, prev, st, rt):
    raw = None
    if   dp==UP   and dc==UP:   raw =  1
    elif dp==DOWN and dc==DOWN: raw = -1
    elif dp==UP   and dc==DOWN: raw = -1
    elif dp==DOWN and dc==UP:   raw =  1
    elif (dp==FLAT or dp==UP)   and (dc==UP   or dc==FLAT): return 1
    elif (dp==FLAT or dp==DOWN) and (dc==DOWN or dc==FLAT): return 0
    elif dp==FLAT and dc==FLAT: return prev
    else: return prev
    diff = abs(ac - ap); thr2 = st if (dp>0)==(dc>0) else rt
    if diff < thr2: return prev
    return max(raw, 0)

def build_v2_signals(d, s_thr, r_thr):
    d = d.copy()
    d['wk'] = d['date'].dt.to_period('W')
    o = d['open'].values; h = d['high'].values
    l = d['low'].values;  c = d['close'].values
    n = len(d)

    # WTS
    def agg_w(g):
        g = g.sort_values('date')
        return pd.Series({'open':g['open'].iloc[0],'high':g['high'].max(),
                          'low':g['low'].min(),'close':g['close'].iloc[-1]})
    wk = d.groupby('wk').apply(agg_w).reset_index().dropna()
    wo=wk['open'].values; wh=wk['high'].values; wl=wk['low'].values; wc=wk['close'].values
    wst=[classify(wo[i],wh[i],wl[i],wc[i],W_FLAT) for i in range(len(wk))]
    wam=amp_pct(wo,wh,wl)
    pos=0; ws=[0]
    for i in range(1,len(wk)):
        pos=seven_rules(wst[i-1],wst[i],wam[i-1],wam[i],pos,W_SAME,W_REV); ws.append(pos)
    wk['wts']=ws
    w2p={str(wk['wk'].iloc[i+1]):wk['wts'].iloc[i] for i in range(len(wk)-1)}
    d['wp']=d['wk'].apply(lambda w:w2p.get(str(w),0))

    # DTS
    ds=[classify(o[i],h[i],l[i],c[i],D_FLAT) for i in range(n)]
    da=amp_pct(o,h,l)
    pos=0; dts=np.empty(n,dtype=int)
    for i in range(n):
        if i==0: dts[i]=0; continue
        pos=seven_rules(ds[i-1],ds[i],da[i-1],da[i],pos,s_thr,r_thr); dts[i]=pos
    dts_s=np.empty(n,dtype=int); dts_s[0]=0; dts_s[1:]=dts[:-1]
    d['dts_s']=dts_s

    # pos_asym_c (v2 confirmed entry)
    wp=d['wp'].values; pos_c=0; prev_w=0; ac=[]
    for i in range(n):
        w=int(wp[i]); dt=int(dts_s[i])
        if w==0: pos_c=0
        elif prev_w==0 and w==1:
            if dt==1: pos_c=1
        else:
            if   pos_c==1 and dt==0: pos_c=0
            elif pos_c==0 and dt==1: pos_c=1
        ac.append(pos_c); prev_w=w
    d['pos_v2']=ac
    return d

# ─────────────────────────────────────────────
# 策略2: 双均线 MA5/MA20
# ─────────────────────────────────────────────
def build_dual_ma(d, fast=5, slow=20):
    d = d.copy()
    d['ma_fast'] = d['close'].rolling(fast).mean()
    d['ma_slow'] = d['close'].rolling(slow).mean()
    # 金叉=1, 死叉=0; 使用前一日信号（避免look-ahead）
    sig = (d['ma_fast'] > d['ma_slow']).astype(int)
    d['pos_dual_ma'] = sig.shift(1).fillna(0).astype(int)
    return d

# ─────────────────────────────────────────────
# 策略3: 多周期共振 周MA20过滤 + 日MA5触发
# ─────────────────────────────────────────────
def build_multi_tf(d, daily_ma=5, weekly_ma=20):
    d = d.copy()
    # 周线收盘 (每周最后一个交易日)
    d['wk'] = d['date'].dt.to_period('W')
    wk_close = d.groupby('wk')['close'].last()
    wk_ma = wk_close.rolling(weekly_ma).mean()
    wk_bull = (wk_close > wk_ma).astype(int)
    # 映射回日线：周信号用前一周（shift(1)）
    wk_bull_shifted = wk_bull.shift(1).fillna(0)
    d['wk_bull'] = d['wk'].map(wk_bull_shifted).fillna(0).astype(int)

    # 日线MA5
    d['dma'] = d['close'].rolling(daily_ma).mean()
    day_bull = (d['close'] > d['dma']).astype(int).shift(1).fillna(0).astype(int)
    d['pos_multi_tf'] = ((d['wk_bull'] == 1) & (day_bull == 1)).astype(int)
    return d

# ─────────────────────────────────────────────
# 策略4: 海龟 Donchian 突破
# ─────────────────────────────────────────────
def build_turtle(d, entry_n=20, exit_n=10):
    d = d.copy()
    d['don_high'] = d['close'].rolling(entry_n).max().shift(1)   # 前N日最高
    d['don_low']  = d['close'].rolling(exit_n).min().shift(1)    # 前N日最低

    pos = 0; positions = []
    for i, row in d.iterrows():
        c = row['close']
        if pd.isna(row['don_high']) or pd.isna(row['don_low']):
            positions.append(0); continue
        if pos == 0 and c > row['don_high']:
            pos = 1
        elif pos == 1 and c < row['don_low']:
            pos = 0
        positions.append(pos)
    # 收盘产生信号 → 次日开盘成交（避免当日 look-ahead）
    d['pos_turtle'] = pd.Series(positions).shift(1).fillna(0).astype(int)
    return d

# ─────────────────────────────────────────────
# Backtest engine
# ─────────────────────────────────────────────
def backtest(d, pos_col, init=1_000_000.0):
    opens = d['open'].values; closes = d['close'].values
    pos_arr = d[pos_col].values
    cash=init; shares=0.0; prev=0; ep=0.0; ed=None; equity=[]; trades=[]

    for i in range(len(d)):
        np_=int(pos_arr[i]); o=opens[i]; c=closes[i]
        if np_!=prev:
            if prev==1 and shares>0:
                cash=shares*o*(1-COST_BPS/10000)
                pnl=(o*(1-COST_BPS/10000)-ep)/ep*100
                trades.append({'entry_date':str(ed.date()),'exit_date':str(d['date'].iloc[i].date()),
                    'entry_price':round(ep,4),'exit_price':round(o,4),
                    'pnl_pct':round(pnl,2),'hold_days':(d['date'].iloc[i]-ed).days})
                shares=0.0
            if np_==1:
                shares=cash*(1-COST_BPS/10000)/o; cash=0.0
                ep=o*(1+COST_BPS/10000); ed=d['date'].iloc[i]
        prev=np_; equity.append(cash+shares*c)

    if prev==1 and shares>0:
        last=d.iloc[-1]
        pnl=(last['close']*(1-COST_BPS/10000)-ep)/ep*100
        trades.append({'entry_date':str(ed.date()),'exit_date':str(last['date'].date()),
            'entry_price':round(ep,4),'exit_price':round(last['close'],4),
            'pnl_pct':round(pnl,2),'hold_days':(last['date']-ed).days})

    eq=pd.Series(equity); bnh=init*d['close']/d['close'].iloc[0]; n=len(eq)
    tr=(eq.iloc[-1]/init-1)*100; br=(bnh.iloc[-1]/init-1)*100
    dr=eq.pct_change().dropna()
    sh=dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    wins=[t for t in trades if t['pnl_pct']>0]
    return {
        'dates':[str(x.date()) for x in d['date']],
        'close':d['close'].round(4).tolist(),
        'equity':eq.round(2).tolist(),
        'bnh':bnh.round(2).tolist(),
        'cum_ret':((eq/init-1)*100).round(2).tolist(),
        'bnh_ret':((bnh/init-1)*100).round(2).tolist(),
        'pos':pos_arr.tolist(), 'trades':trades,
        'metrics':{
            'total_return':round(tr,2),'bnh_return':round(br,2),'alpha':round(tr-br,2),
            'sharpe':round(sh,2),'max_drawdown':round(mdd,2),
            'win_rate':round(len(wins)/len(trades)*100,1) if trades else 0,
            'n_trades':len(trades),
            'long_pct':round((pos_arr==1).sum()/n*100,1),
            'n_days':n,
        }
    }

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
STRAT_COLS  = ['pos_v2','pos_dual_ma','pos_multi_tf','pos_turtle']
STRAT_NAMES = ['静态v2（本策略）','双均线 MA5/MA20','多周期共振 周MA20+日MA5','海龟CTA N=20/10']

all_data = {}
print(f"{'标的':10s}  {'静态v2':>16s}  {'双均线':>16s}  {'多周期共振':>16s}  {'海龟CTA':>16s}  {'BNH':>8s}")
print('─'*90)

for name in ETF_FILES:
    d = load_etf(name)
    d = d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)

    s, r = STATIC_PARAMS[name]
    d = build_v2_signals(d, s, r)
    d = build_dual_ma(d)
    d = build_multi_tf(d)
    d = build_turtle(d)

    etf = {'name':name,'strategies':{}}
    results = {}
    for col, nm in zip(STRAT_COLS, STRAT_NAMES):
        res = backtest(d, col)
        results[col] = res
        etf['strategies'][col] = {**res, 'label': nm}

    all_data[name] = etf
    m = [results[c]['metrics'] for c in STRAT_COLS]
    bnh = m[0]['bnh_return']
    print(f"{name:10s}  " +
          '  '.join([f"{m[i]['total_return']:+6.1f}%(α{m[i]['alpha']:+.1f})" for i in range(4)]) +
          f"  BNH:{bnh:+5.1f}%")

out = OUTPUT/'strategy_compare_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, default=str)
print(f"\n保存: {out}  ({out.stat().st_size//1024} KB)")
