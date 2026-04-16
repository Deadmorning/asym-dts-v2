#!/usr/bin/env python3
"""
滚动参数优化回测 (Rolling Parameter Optimization)
==================================================
训练窗口: 固定12个月
测试窗口: 季度(3m) / 半年(6m) / 年度(12m)
对比基准: 静态v2参数 + BNH
策略版本: 非对称DTS v2确认版 (pos_asym_c)
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from itertools import product
import warnings
warnings.filterwarnings('ignore')

UPLOADS = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/uploads")
OUTPUT  = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")

W_FLAT=0.015; W_SAME=0.90; W_REV=0.45
D_FLAT=0.005; COST_BPS=15
UP=1; DOWN=-1; FLAT=0

SAME_RANGE = [0.30, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00, 3.50, 4.00, 5.00]
REV_RANGE  = [0.15, 0.30, 0.45, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50]

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

TRAIN_MONTHS = 12
TEST_CONFIGS  = {'quarterly': 3, 'semi_annual': 6, 'annual': 12}
TEST_LABELS   = {'quarterly': '季度滚动(3m)', 'semi_annual': '半年滚动(6m)', 'annual': '年度滚动(12m)'}

# ─────────────────────────────────────────────
# Signal helpers
# ─────────────────────────────────────────────
def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close',
                             '最高':'high','最低':'low','成交量':'volume'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

def classify(o, h, l, c, thr):
    amp = (h - l) / o
    if amp < thr: return FLAT
    return UP if c >= o else DOWN

def amp_pct_v(o, h, l):
    return (h - l) / o * 100.0

def seven_rules(dp, dc, ap, ac, prev_pos, st, rt):
    raw = None
    if   dp==UP   and dc==UP:   raw =  1
    elif dp==DOWN and dc==DOWN: raw = -1
    elif dp==UP   and dc==DOWN: raw = -1
    elif dp==DOWN and dc==UP:   raw =  1
    elif (dp==FLAT or dp==UP)   and (dc==UP   or dc==FLAT): return 1
    elif (dp==FLAT or dp==DOWN) and (dc==DOWN or dc==FLAT): return 0
    elif dp==FLAT and dc==FLAT: return prev_pos
    else: return prev_pos
    diff = abs(ac - ap)
    thr  = st if (dp > 0) == (dc > 0) else rt
    if diff < thr: return prev_pos
    return max(raw, 0)

def compute_wts(d):
    d = d.copy()
    d['wk'] = d['date'].dt.to_period('W')
    opens  = d['open'].values; highs  = d['high'].values
    lows   = d['low'].values;  closes = d['close'].values
    d['ds_tmp'] = [classify(opens[i],highs[i],lows[i],closes[i],W_FLAT) for i in range(len(d))]
    d['da_tmp'] = amp_pct_v(opens, highs, lows)

    def agg_w(g):
        g = g.sort_values('date')
        idx = g.index.tolist()
        return pd.Series({
            'open':  g['open'].iloc[0],   'high':  g['high'].max(),
            'low':   g['low'].min(),       'close': g['close'].iloc[-1]})

    wk = d.groupby('wk').apply(agg_w).reset_index().dropna()
    wo = wk['open'].values; wh = wk['high'].values
    wl = wk['low'].values;  wc = wk['close'].values
    wst = [classify(wo[i],wh[i],wl[i],wc[i],W_FLAT) for i in range(len(wk))]
    wam = amp_pct_v(wo, wh, wl)

    pos=0; ws=[0]
    for i in range(1, len(wk)):
        np_ = seven_rules(wst[i-1], wst[i], wam[i-1], wam[i], pos, W_SAME, W_REV)
        ws.append(np_); pos=np_
    wk['wts'] = ws
    wk_list = wk['wk'].tolist(); wts_list = wk['wts'].tolist()
    w2p = {str(wk_list[i+1]): wts_list[i] for i in range(len(wk_list)-1)}
    d['wp'] = d['wk'].apply(lambda w: w2p.get(str(w), 0))
    return d.drop(columns=['ds_tmp','da_tmp','wk'])

def compute_all_signals(d):
    """Precompute pos_asym_c for every (SAME, REV) combination."""
    opens  = d['open'].values; highs  = d['high'].values
    lows   = d['low'].values;  closes = d['close'].values
    wp     = d['wp'].values
    n      = len(d)

    ds = np.array([classify(opens[i],highs[i],lows[i],closes[i],D_FLAT) for i in range(n)])
    da = amp_pct_v(opens, highs, lows)

    all_sig = {}
    for s, r in product(SAME_RANGE, REV_RANGE):
        # DTS signal
        pos=0; dts=np.empty(n, dtype=int)
        for i in range(n):
            if i==0: dts[i]=0; continue
            pos = seven_rules(ds[i-1], ds[i], da[i-1], da[i], pos, s, r)
            dts[i] = pos
        dts_s = np.empty(n, dtype=int)
        dts_s[0]=0; dts_s[1:]=dts[:-1]

        # pos_asym_c (confirmed-entry variant)
        pos_c=0; prev_w=0; ac=np.empty(n, dtype=int)
        for i in range(n):
            w=int(wp[i]); dt=int(dts_s[i])
            if w==0: pos_c=0
            elif prev_w==0 and w==1:
                if dt==1: pos_c=1
            else:
                if   pos_c==1 and dt==0: pos_c=0
                elif pos_c==0 and dt==1: pos_c=1
            ac[i]=pos_c; prev_w=w

        all_sig[(s,r)] = ac
    return all_sig

# ─────────────────────────────────────────────
# Backtest helpers
# ─────────────────────────────────────────────
def quick_return(opens, closes, pos_arr):
    """Fast return on a position array slice (index-aligned)."""
    cash=1.0; shares=0.0; prev=0
    for i in range(len(pos_arr)):
        np_=int(pos_arr[i]); o=opens[i]; c=closes[i]
        if np_!=prev:
            if prev==1 and shares>0:
                cash=shares*o*(1-COST_BPS/10000); shares=0.0
            if np_==1:
                shares=cash*(1-COST_BPS/10000)/o; cash=0.0
        prev=np_
    if prev==1 and shares>0:
        cash=shares*closes[-1]*(1-COST_BPS/10000)
    return cash-1.0

def optimize_window(opens_tr, closes_tr, all_sig, idx_tr):
    """Grid search best (SAME, REV) on training index slice."""
    best=-np.inf; best_key=None
    for key, sig in all_sig.items():
        ret = quick_return(opens_tr, closes_tr, sig[idx_tr])
        if ret>best: best=ret; best_key=key
    return best_key

def build_rolling_pos(d, all_sig, train_months, test_months):
    dates  = d['date']
    opens  = d['open'].values; closes = d['close'].values
    n      = len(d)
    final  = np.zeros(n, dtype=int)
    plog   = []

    start_date     = dates.iloc[0]
    first_test_start = start_date + pd.DateOffset(months=train_months)
    end_date       = dates.iloc[-1]
    test_start     = first_test_start

    while test_start <= end_date:
        test_end = min(test_start + pd.DateOffset(months=test_months) - pd.Timedelta(days=1), end_date)
        train_start = test_start - pd.DateOffset(months=train_months)
        train_end   = test_start - pd.Timedelta(days=1)

        idx_tr = np.where((dates>=train_start)&(dates<=train_end))[0]
        idx_te = np.where((dates>=test_start) &(dates<=test_end))[0]

        if len(idx_tr)>=50 and len(idx_te)>=5:
            bk = optimize_window(opens[idx_tr], closes[idx_tr], all_sig, idx_tr)
            final[idx_te] = all_sig[bk][idx_te]
            plog.append({'test_start': str(test_start.date()), 'test_end': str(test_end.date()),
                         'same': bk[0], 'rev': bk[1]})

        test_start += pd.DateOffset(months=test_months)

    return final, plog

def full_backtest(d, pos_arr, init=1_000_000.0):
    opens  = d['open'].values; closes = d['close'].values
    cash=init; shares=0.0; pos=0; ep=0.0; ed=None; equity=[]; trades=[]

    for i in range(len(d)):
        np_=int(pos_arr[i]); o=opens[i]; c=closes[i]
        if np_!=pos:
            if pos==1 and shares>0:
                cash=shares*o*(1-COST_BPS/10000)
                pnl=(o*(1-COST_BPS/10000)-ep)/ep*100
                trades.append({'entry_date':str(ed.date()),'exit_date':str(d['date'].iloc[i].date()),
                    'entry_price':round(ep,4),'exit_price':round(o,4),
                    'pnl_pct':round(pnl,2),'hold_days':(d['date'].iloc[i]-ed).days})
                shares=0.0
            if np_==1:
                shares=cash*(1-COST_BPS/10000)/o; cash=0.0
                ep=o*(1+COST_BPS/10000); ed=d['date'].iloc[i]
        pos=np_; equity.append(cash+shares*c)

    if pos==1 and shares>0:
        last=d.iloc[-1]
        pnl=(last['close']*(1-COST_BPS/10000)-ep)/ep*100
        trades.append({'entry_date':str(ed.date()),'exit_date':str(last['date'].date()),
            'entry_price':round(ep,4),'exit_price':round(last['close'],4),
            'pnl_pct':round(pnl,2),'hold_days':(last['date']-ed).days})

    eq=pd.Series(equity); bnh=init*d['close']/d['close'].iloc[0]; n2=len(eq)
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
            'long_pct':round((pos_arr==1).sum()/n2*100,1),
            'n_days':n2,
        }
    }

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
all_data = {}
FULL_START = '2023-04-17'; FULL_END = '2026-04-15'

header = f"{'标的':10s}  {'静态v2':>16s}  {'季度滚动':>16s}  {'半年滚动':>16s}  {'年度滚动':>16s}  {'BNH':>8s}"
print(header)
print("─" * 90)

for name in ETF_FILES:
    print(f"\n[{name}] 载入并预计算信号...", flush=True)
    d = load_etf(name)
    d = d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)
    d = compute_wts(d)

    all_sig = compute_all_signals(d)

    etf_data = {'name': name, 'strategies': {}}

    # Static v2
    sk = STATIC_PARAMS[name]
    r_static = full_backtest(d, all_sig[sk])
    etf_data['strategies']['static_v2'] = {**r_static, 'label': '静态v2参数'}

    # Rolling frequencies
    for freq, test_m in TEST_CONFIGS.items():
        print(f"  {TEST_LABELS[freq]}: 优化中...", end=' ', flush=True)
        roll_pos, plog = build_rolling_pos(d, all_sig, TRAIN_MONTHS, test_m)
        r_roll = full_backtest(d, roll_pos)
        etf_data['strategies'][freq] = {**r_roll, 'label': TEST_LABELS[freq], 'param_log': plog}
        m = r_roll['metrics']
        print(f"总收益{m['total_return']:+.1f}% α{m['alpha']:+.1f}%")

    all_data[name] = etf_data

    # Summary row
    ms = r_static['metrics']
    mq = etf_data['strategies']['quarterly']['metrics']
    mh = etf_data['strategies']['semi_annual']['metrics']
    ma = etf_data['strategies']['annual']['metrics']
    print(f"{name:10s}  "
          f"静v2:{ms['total_return']:+6.1f}%(α{ms['alpha']:+.1f})  "
          f"季度:{mq['total_return']:+6.1f}%(α{mq['alpha']:+.1f})  "
          f"半年:{mh['total_return']:+6.1f}%(α{mh['alpha']:+.1f})  "
          f"年度:{ma['total_return']:+6.1f}%(α{ma['alpha']:+.1f})  "
          f"BNH:{ms['bnh_return']:+6.1f}%")

out = OUTPUT / 'rolling_params_results.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, default=str)
print(f"\n结果已保存: {out}  ({out.stat().st_size//1024} KB)")
