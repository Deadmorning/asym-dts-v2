"""
分阶段资金对比：熊市保住本金 → 牛市复利优势
================================================
以100万起始资金，分两阶段对比：
  熊市：2023-04-17 ~ 2024-09-20（2024年9月行情前）
  牛市：2024-09-23 ~ 2026-04-15（9月急涨后）
  全程：链式（熊市末资金作为牛市起始资金）

策略：pos_asym_new（v2新参数非对称DTS）vs BNH
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

NEW_PARAMS = {
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

PHASES = [
    ("全程",  "2023-04-17", "2026-04-15"),
    ("熊市",  "2023-04-17", "2024-09-20"),
    ("牛市",  "2024-09-23", "2026-04-15"),
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

def build_signals(daily, new_s, new_r):
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

    d['ds'] = d.apply(lambda r: classify(r, D_FLAT), axis=1)
    d['da'] = d.apply(amp_pct, axis=1)
    pos = 0; dsigs = [0]
    for i in range(1, len(d)):
        p, c = d.iloc[i-1], d.iloc[i]
        np_, _, _ = seven_rules(p['ds'], c['ds'], p['da'], c['da'], pos, new_s, new_r)
        dsigs.append(np_); pos = np_
    d['dts'] = dsigs
    d['dts_s'] = d['dts'].shift(1).fillna(0).astype(int)

    asym = []; pos_a = 0; prev_wp = 0
    for i, row in d.iterrows():
        wp = int(row['wp']); dts = int(row['dts_s'])
        if wp == 0: pos_a = 0
        elif prev_wp == 0 and wp == 1: pos_a = 1
        else:
            if   pos_a == 1 and dts == 0: pos_a = 0
            elif pos_a == 0 and dts == 1: pos_a = 1
        asym.append(pos_a); prev_wp = wp
    d['pos_asym'] = asym
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
            'pnl_pct': round(pnl,2), 'hold_days': (last['date']-ed).days})
    eq = pd.Series(equity)
    bnh = init * d['close'] / d['close'].iloc[0]
    n = len(eq)
    tr = (eq.iloc[-1]/init-1)*100; br = (bnh.iloc[-1]/init-1)*100
    dr = eq.pct_change().dropna()
    sh = dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd = ((eq-eq.cummax())/eq.cummax()).min()*100
    return {
        'dates': [str(x.date()) for x in d['date']],
        'cum_ret': ((eq/init-1)*100).round(2).tolist(),
        'bnh_ret': ((bnh/init-1)*100).round(2).tolist(),
        'equity': eq.round(2).tolist(),
        'bnh': bnh.round(2).tolist(),
        'end_equity': round(eq.iloc[-1], 2),
        'end_bnh': round(bnh.iloc[-1], 2),
        'metrics': {
            'total_return': round(tr,2), 'bnh_return': round(br,2),
            'alpha': round(tr-br,2), 'sharpe': round(sh,2),
            'max_drawdown': round(mdd,2),
            'n_trades': len(trades), 'long_pct': round((d[pos_col]==1).sum()/n*100,1),
            'start': str(d['date'].iloc[0].date()), 'end': str(d['date'].iloc[-1].date()),
        }
    }

# === 主流程 ===
INIT = 1_000_000.0
all_data = {}

print(f"{'标的':10s}  {'阶段':5s}  {'策略收益':>8s}  {'策略末资金':>12s}  {'BNH收益':>8s}  {'BNH末资金':>12s}  {'超额α':>8s}")
print("─" * 85)

for name in ETF_FILES:
    new_s, new_r = NEW_PARAMS[name]
    daily = load_etf(name)
    dsig  = build_signals(daily, new_s, new_r)

    etf = {'phases': {}}

    for plabel, ps, pe in PHASES:
        r_asym = backtest_seg(dsig, 'pos_asym', ps, pe, INIT)
        r_wts  = backtest_seg(dsig, 'pos_wts', ps, pe, INIT)
        if r_asym and r_wts:
            etf['phases'][plabel] = {
                'asym': r_asym,
                'wts': r_wts,
            }
            m = r_asym['metrics']
            mw = r_wts['metrics']
            print(f"{name:10s}  {plabel:5s}  {m['total_return']:+7.1f}%  {r_asym['end_equity']:>12,.0f}  "
                  f"{m['bnh_return']:+7.1f}%  {r_wts['end_bnh']:>12,.0f}  {m['alpha']:+7.1f}%")
    print()

    # === 链式资金：熊市末资金 → 牛市起始 ===
    bear_asym = etf['phases'].get('熊市', {}).get('asym')
    bear_wts  = etf['phases'].get('熊市', {}).get('wts')
    bull_start_asym = bear_asym['end_equity'] if bear_asym else INIT
    bull_start_bnh  = bear_wts['end_bnh']     if bear_wts  else INIT

    bull_asym_chain = backtest_seg(dsig, 'pos_asym', '2024-09-23', '2026-04-15', bull_start_asym)
    bull_bnh_chain  = backtest_seg(dsig, 'pos_wts',  '2024-09-23', '2026-04-15', bull_start_bnh)

    if bull_asym_chain and bull_bnh_chain:
        etf['chain'] = {
            'bear_end_asym': bull_start_asym,
            'bear_end_bnh': bull_start_bnh,
            'bull_asym': bull_asym_chain,
            'bull_bnh': bull_bnh_chain,
            'final_asym': round(bull_asym_chain['end_equity'], 2),
            'final_bnh': round(bull_bnh_chain['end_bnh'], 2),
        }
        adv = bull_asym_chain['end_equity'] - bull_bnh_chain['end_bnh']
        print(f"  {name} 链式：熊市末策略{bull_start_asym/10000:.1f}万 vs BNH{bull_start_bnh/10000:.1f}万 "
              f"→ 牛市末策略{bull_asym_chain['end_equity']/10000:.1f}万 vs BNH{bull_bnh_chain['end_bnh']/10000:.1f}万 "
              f"(多{adv/10000:+.1f}万)")
    print()

    all_data[name] = etf

out = OUTPUT / 'phase_comparison.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, default=str)
print(f"\n保存: {out}  ({out.stat().st_size // 1024} KB)")
