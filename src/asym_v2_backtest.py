"""
非对称DTS v2 — 使用针对非对称策略重新优化的参数
================================================
对比：
  pos_asym_old  — 旧参数非对称DTS（对称DTS优化参数）
  pos_asym_new  — 新参数非对称DTS（专为非对称重新优化）
  pos_asym_c    — 新参数 + 入场确认（新多头周需 dts_s=1 才入场）
  pos_wts       — 纯WTS（基准）
  BNH           — 买入持有
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

UPLOADS = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/uploads")
OUTPUT  = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")

W_FLAT=0.015; W_SAME=0.90; W_REV=0.45
D_FLAT=0.005; COST_BPS=15
UP=1; DOWN=-1; FLAT=0

# 旧参数（对称DTS优化）
OLD_PARAMS = {
    "上证50ETF":  (0.75, 0.60),
    "沪深300ETF": (2.50, 2.00),
    "中证500ETF": (2.50, 2.00),
    "科创50ETF":  (2.50, 1.50),
    "深证100ETF": (3.00, 2.00),
    "创业板ETF":  (4.00, 1.00),
}
# 新参数（专为非对称策略优化）
NEW_PARAMS = {
    "上证50ETF":  (1.50, 2.50),   # 旧 0.75/0.60 → α+7.9%
    "沪深300ETF": (2.50, 2.50),   # 旧 2.50/2.00 → 微幅改善
    "中证500ETF": (2.50, 2.50),   # 旧 2.50/2.00 → α+21.4%
    "科创50ETF":  (2.50, 1.50),   # 不变，原版不改
    "深证100ETF": (3.00, 2.00),   # 不变，已最优
    "创业板ETF":  (4.00, 1.00),   # 不变，无改善
}
ETF_FILES = {
    "上证50ETF":  "510050_上证_50ETF.csv",
    "沪深300ETF": "510300_沪深_300ETF.csv",
    "中证500ETF": "510500_中证_500ETF.csv",
    "科创50ETF":  "588080_科创_50ETF.csv",
    "深证100ETF": "159901_深证_100ETF.csv",
    "创业板ETF":  "159915_创业板_ETF.csv",
}
PERIODS = [
    ("全程", "2023-04-17", "2026-04-15"),
    ("P1",   "2025-01-01", "2025-08-31"),
    ("P2",   "2025-08-01", "2026-01-31"),
    ("P3",   "2025-08-01", "2026-03-31"),
]

def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close',
                             '最高':'high','最低':'low','成交量':'volume'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

def classify(row, thr):
    amp = (row['high'] - row['low']) / row['open']
    if amp < thr: return FLAT
    return UP if row['close'] >= row['open'] else DOWN

def amp_pct(row):
    return (row['high'] - row['low']) / row['open'] * 100.0

def seven_rules(dp, dc, ap, ac, prev_pos, st, rt):
    raw = None
    if   dp==UP   and dc==UP:   rule, raw = 1,  1
    elif dp==DOWN and dc==DOWN: rule, raw = 2, -1
    elif dp==UP   and dc==DOWN: rule, raw = 3, -1
    elif dp==DOWN and dc==UP:   rule, raw = 4,  1
    elif (dp==FLAT or dp==UP)   and (dc==UP   or dc==FLAT): return 1, 5, False
    elif (dp==FLAT or dp==DOWN) and (dc==DOWN or dc==FLAT): return 0, 6, False
    elif dp==FLAT and dc==FLAT: return prev_pos, 7, False
    else: return prev_pos, None, False
    diff = abs(ac - ap); thr = st if (dp > 0) == (dc > 0) else rt
    if diff < thr: return prev_pos, rule, True
    return max(raw, 0), rule, False

def build_signals(daily, old_s, old_r, new_s, new_r):
    d = daily.copy()
    d['wk'] = d['date'].dt.to_period('W')

    def agg_w(g):
        g = g.sort_values('date')
        return pd.Series({'we': g['date'].iloc[-1],
            'open': g['open'].iloc[0], 'high': g['high'].max(),
            'low': g['low'].min(), 'close': g['close'].iloc[-1]})

    wk = d.groupby('wk').apply(agg_w).reset_index().dropna()
    wk['st'] = wk.apply(lambda r: classify(r, W_FLAT), axis=1)
    wk['am'] = wk.apply(amp_pct, axis=1)
    pos = 0; ws = [0]
    for i in range(1, len(wk)):
        p, c = wk.iloc[i-1], wk.iloc[i]
        np_, _, _ = seven_rules(p['st'], c['st'], p['am'], c['am'], pos, W_SAME, W_REV)
        ws.append(np_); pos = np_
    wk['wts'] = ws
    wk_list = wk['wk'].tolist(); wts_list = wk['wts'].tolist()
    w2p = {str(wk_list[i+1]): wts_list[i] for i in range(len(wk_list)-1)}
    d['wp'] = d['wk'].apply(lambda w: w2p.get(str(w), 0))

    def make_dts(d_same, d_rev, suffix):
        d['ds'] = d.apply(lambda r: classify(r, D_FLAT), axis=1)
        d['da'] = d.apply(amp_pct, axis=1)
        pos = 0; dsigs = [0]
        for i in range(1, len(d)):
            p, c = d.iloc[i-1], d.iloc[i]
            np_, _, _ = seven_rules(p['ds'], c['ds'], p['da'], c['da'], pos, d_same, d_rev)
            dsigs.append(np_); pos = np_
        dts_col  = f'dts{suffix}'
        dtss_col = f'dts_s{suffix}'
        d[dts_col]  = dsigs
        d[dtss_col] = d[dts_col].shift(1).fillna(0).astype(int)

        # 非对称原版
        asym = []; pos_a = 0; prev_wp = 0
        for i, row in d.iterrows():
            wp = int(row['wp']); dts = int(row[dtss_col])
            if wp == 0: pos_a = 0
            elif prev_wp == 0 and wp == 1: pos_a = 1
            else:
                if   pos_a == 1 and dts == 0: pos_a = 0
                elif pos_a == 0 and dts == 1: pos_a = 1
            asym.append(pos_a); prev_wp = wp
        d[f'pos_asym{suffix}'] = asym

        # 确认版（新多头周需 dts_s=1 才入场）
        asym_c = []; pos_c = 0; prev_wc = 0
        for i, row in d.iterrows():
            wp = int(row['wp']); dts = int(row[dtss_col])
            if wp == 0: pos_c = 0
            elif prev_wc == 0 and wp == 1:
                if dts == 1: pos_c = 1
            else:
                if   pos_c == 1 and dts == 0: pos_c = 0
                elif pos_c == 0 and dts == 1: pos_c = 1
            asym_c.append(pos_c); prev_wc = wp
        d[f'pos_asym_c{suffix}'] = asym_c

    make_dts(old_s, old_r, '_old')
    make_dts(new_s, new_r, '_new')

    d['pos_wts'] = d['wp']
    return d


def backtest_seg(daily_full, pos_col, start, end, init=1_000_000.0):
    d = daily_full[(daily_full['date'] >= start) & (daily_full['date'] <= end)].copy().reset_index(drop=True)
    if len(d) < 5: return None
    cash = init; shares = 0.0; pos = 0; trades = []; ep = 0.0; ed = None; equity = []
    for i, row in d.iterrows():
        np_ = int(row[pos_col]); o = row['open']; c = row['close']
        if np_ != pos:
            if pos == 1 and shares > 0:
                cash = shares * o * (1 - COST_BPS/10000)
                pnl  = (o*(1-COST_BPS/10000)-ep)/ep*100
                trades.append({'entry_date': str(ed.date()), 'exit_date': str(row['date'].date()),
                    'entry_price': round(ep,4), 'exit_price': round(o,4),
                    'pnl_pct': round(pnl,2), 'hold_days': (row['date']-ed).days})
                shares = 0.0
            if np_ == 1:
                shares = (cash*(1-COST_BPS/10000))/o; cash=0.0
                ep = o*(1+COST_BPS/10000); ed = row['date']
        pos = np_; equity.append(cash + shares*c)
    if pos == 1 and shares > 0:
        last = d.iloc[-1]
        pnl = (last['close']*(1-COST_BPS/10000)-ep)/ep*100
        trades.append({'entry_date': str(ed.date()), 'exit_date': str(last['date'].date()),
            'entry_price': round(ep,4), 'exit_price': round(last['close'],4),
            'pnl_pct': round(pnl,2), 'hold_days': (last['date']-ed).days})
    eq = pd.Series(equity); bnh = init*d['close']/d['close'].iloc[0]; n = len(eq)
    tr = (eq.iloc[-1]/init-1)*100; br = (bnh.iloc[-1]/init-1)*100
    dr = eq.pct_change().dropna()
    sh = dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd = ((eq-eq.cummax())/eq.cummax()).min()*100
    wins = [t for t in trades if t['pnl_pct'] > 0]
    return {
        'dates': [str(x.date()) for x in d['date']], 'close': d['close'].round(4).tolist(),
        'equity': eq.round(2).tolist(), 'bnh': bnh.round(2).tolist(),
        'cum_ret': ((eq/init-1)*100).round(2).tolist(), 'bnh_ret': ((bnh/init-1)*100).round(2).tolist(),
        'pos': d[pos_col].tolist(), 'trades': trades,
        'metrics': {
            'total_return': round(tr,2), 'bnh_return': round(br,2), 'alpha': round(tr-br,2),
            'sharpe': round(sh,2), 'max_drawdown': round(mdd,2),
            'win_rate': round(len(wins)/len(trades)*100,1) if trades else 0,
            'n_trades': len(trades), 'long_pct': round((d[pos_col]==1).sum()/n*100,1),
            'n_days': n, 'start': str(d['date'].iloc[0].date()), 'end': str(d['date'].iloc[-1].date()),
        }
    }


STRATS = [
    ('pos_asym_new', '非对称v2（新参数）'),
    ('pos_asym_c_new', '非对称v2确认版'),
    ('pos_asym_old', '非对称v1（旧参数）'),
    ('pos_wts',      '纯WTS'),
]

all_data = {}

print(f"{'标的':10s} {'阶段':8s}  "
      f"{'v2新参':>12s}  {'v2确认':>12s}  {'v1旧参':>12s}  {'纯WTS':>8s}  {'BNH':>8s}")
print("─" * 82)

for name in ETF_FILES:
    old_s, old_r = OLD_PARAMS[name]
    new_s, new_r = NEW_PARAMS[name]
    daily = load_etf(name)
    dsig  = build_signals(daily, old_s, old_r, new_s, new_r)

    etf = {
        'old_params': {'same': old_s, 'rev': old_r},
        'new_params': {'same': new_s, 'rev': new_r},
        'params_changed': (old_s != new_s or old_r != new_r),
        'periods': {}
    }

    for plabel, ps, pe in PERIODS:
        results = {}
        for col, lbl in STRATS:
            r = backtest_seg(dsig, col, ps, pe)
            results[col] = r
        etf['periods'][plabel] = results

        if results['pos_wts']:
            mw   = results['pos_wts']['metrics']
            mv2  = results['pos_asym_new']['metrics']
            mv2c = results['pos_asym_c_new']['metrics']
            mv1  = results['pos_asym_old']['metrics']
            print(f"{name:10s} {plabel:8s}  "
                  f"v2 {mv2['total_return']:+6.1f}%(α{mv2['alpha']:+.1f})  "
                  f"v2c {mv2c['total_return']:+6.1f}%(α{mv2c['alpha']:+.1f})  "
                  f"v1 {mv1['total_return']:+6.1f}%(α{mv1['alpha']:+.1f})  "
                  f"WTS {mw['total_return']:+5.1f}%  "
                  f"BNH {mw['bnh_return']:+5.1f}%")

    all_data[name] = etf
    print()

out = OUTPUT / 'asym_v2_results.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, default=str)
print(f"\n保存: {out}  ({out.stat().st_size // 1024} KB)")
