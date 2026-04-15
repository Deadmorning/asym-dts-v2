"""
非对称DTS参数优化
================
当前参数来自对称DTS优化，非对称版的最优参数可能不同。
本脚本对非对称策略重新做网格搜索。

同时对比：
  A. 非对称原版（立即入场）
  B. 非对称确认版（新多头周需 dts_s=1 才入场）
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

# 现有最优参数（对称DTS优化结果）
OLD_PARAMS = {
    "上证50ETF":  (0.75, 0.60),
    "沪深300ETF": (2.50, 2.00),
    "中证500ETF": (2.50, 2.00),
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

# 网格搜索空间
SAME_RANGE = [0.30, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00, 3.50, 4.00, 5.00]
REV_RANGE  = [0.15, 0.30, 0.45, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50]
MIN_TRADES = 3

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

def build_weekly_perm(daily):
    """计算周线 WTS 许可信号（固定，不依赖日线参数）"""
    d = daily.copy()
    d['wk'] = d['date'].dt.to_period('W')
    def agg_w(g):
        g = g.sort_values('date')
        return pd.Series({'we': g['date'].iloc[-1],
            'open': g['open'].iloc[0], 'high': g['high'].max(),
            'low': g['low'].min(),     'close': g['close'].iloc[-1]})
    wk = d.groupby('wk').apply(agg_w).reset_index().dropna()
    wk['st'] = wk.apply(lambda r: classify(r, W_FLAT), axis=1)
    wk['am'] = wk.apply(amp_pct, axis=1)
    pos = 0; ws = [0]
    for i in range(1, len(wk)):
        p, c = wk.iloc[i-1], wk.iloc[i]
        np_, _, _ = seven_rules(p['st'], c['st'], p['am'], c['am'], pos, W_SAME, W_REV)
        ws.append(np_); pos = np_
    wk['wts'] = ws
    wk_list  = wk['wk'].tolist(); wts_list = wk['wts'].tolist()
    w2p = {str(wk_list[i+1]): wts_list[i] for i in range(len(wk_list)-1)}
    d['wp'] = d['wk'].apply(lambda w: w2p.get(str(w), 0))
    return d

def build_dts(d_with_wp, d_same, d_rev):
    """在给定日线参数下计算 DTS 信号和两种仓位"""
    d = d_with_wp.copy()
    d['ds'] = d.apply(lambda r: classify(r, D_FLAT), axis=1)
    d['da'] = d.apply(amp_pct, axis=1)
    pos = 0; dsigs = [0]
    for i in range(1, len(d)):
        p, c = d.iloc[i-1], d.iloc[i]
        np_, _, _ = seven_rules(p['ds'], c['ds'], p['da'], c['da'], pos, d_same, d_rev)
        dsigs.append(np_); pos = np_
    d['dts'] = dsigs
    d['dts_s'] = d['dts'].shift(1).fillna(0).astype(int)

    # 非对称原版（立即入场）
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

    # 非对称确认版（新多头周需 dts_s=1 才入场）
    asym_c = []; pos_c = 0; prev_wc = 0
    for i, row in d.iterrows():
        wp = int(row['wp']); dts = int(row['dts_s'])
        if wp == 0:
            pos_c = 0
        elif prev_wc == 0 and wp == 1:
            # 新多头周：只有 dts_s=1 才入场，否则等待
            if dts == 1: pos_c = 1
            # else: 保持 pos_c=0，等到 dts_s=1 才入场
        else:
            # 已在多头周内（和原版相同逻辑）
            if   pos_c == 1 and dts == 0: pos_c = 0
            elif pos_c == 0 and dts == 1: pos_c = 1
        asym_c.append(pos_c); prev_wc = wp
    d['pos_asym_c'] = asym_c
    return d


def backtest_fast(d, pos_col, start, end, init=1_000_000.0):
    seg = d[(d['date'] >= start) & (d['date'] <= end)].reset_index(drop=True)
    if len(seg) < 5: return None
    cash = init; shares = 0.0; pos = 0; trades = 0
    ep = 0.0; equity = []
    for _, row in seg.iterrows():
        np_ = int(row[pos_col]); o = row['open']; c = row['close']
        if np_ != pos:
            if pos == 1 and shares > 0:
                cash = shares * o * (1 - COST_BPS/10000); shares = 0.0; trades += 1
            if np_ == 1:
                shares = (cash*(1-COST_BPS/10000))/o; cash = 0.0; ep = o*(1+COST_BPS/10000)
        pos = np_; equity.append(cash + shares*c)
    if pos == 1 and shares > 0: trades += 1
    eq = pd.Series(equity)
    bnh = init * seg['close'] / seg['close'].iloc[0]
    tr = (eq.iloc[-1]/init-1)*100; br = (bnh.iloc[-1]/init-1)*100
    dr = eq.pct_change().dropna()
    sh = dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd = ((eq - eq.cummax())/eq.cummax()).min()*100
    return {'alpha': round(tr-br, 3), 'total_r': round(tr, 3),
            'sharpe': round(sh, 3), 'mdd': round(mdd, 3),
            'n_trades': trades, 'long_pct': round((seg[pos_col]==1).sum()/len(seg)*100, 1)}


# ── 主流程 ────────────────────────────────────────────────────────────────────
PS, PE = "2023-04-17", "2026-04-15"
new_params = {}

print(f"\n{'='*80}")
print(f"非对称DTS参数优化（{len(SAME_RANGE)}×{len(REV_RANGE)}={len(SAME_RANGE)*len(REV_RANGE)} 组合/ETF）")
print(f"{'='*80}\n")

for name in ETF_FILES:
    daily = load_etf(name)
    d_wp  = build_weekly_perm(daily)
    old_s, old_r = OLD_PARAMS[name]

    results = {}
    for d_same in SAME_RANGE:
        for d_rev in REV_RANGE:
            dsig = build_dts(d_wp, d_same, d_rev)
            for variant, col in [('asym', 'pos_asym'), ('asym_c', 'pos_asym_c')]:
                r = backtest_fast(dsig, col, PS, PE)
                if r and r['n_trades'] >= MIN_TRADES:
                    key = (d_same, d_rev, variant)
                    results[key] = r

    # 原版非对称：找最优
    asym_results = {k: v for k, v in results.items() if k[2]=='asym'}
    best_asym_key = max(asym_results, key=lambda k: asym_results[k]['alpha']) if asym_results else None

    # 确认版非对称：找最优
    asym_c_results = {k: v for k, v in results.items() if k[2]=='asym_c'}
    best_asym_c_key = max(asym_c_results, key=lambda k: asym_c_results[k]['alpha']) if asym_c_results else None

    # 旧参数的两个版本
    old_asym   = results.get((old_s, old_r, 'asym'))
    old_asym_c = results.get((old_s, old_r, 'asym_c'))

    print(f"─── {name} (原始参数 SAME={old_s}/REV={old_r}) ───")
    if old_asym:
        print(f"  旧参数-原版:  α={old_asym['alpha']:+.2f}%  收益={old_asym['total_r']:+.1f}%  T={old_asym['n_trades']}笔  夏普={old_asym['sharpe']:.2f}")
    if old_asym_c:
        print(f"  旧参数-确认:  α={old_asym_c['alpha']:+.2f}%  收益={old_asym_c['total_r']:+.1f}%  T={old_asym_c['n_trades']}笔  夏普={old_asym_c['sharpe']:.2f}")
    if best_asym_key:
        b = asym_results[best_asym_key]
        print(f"  新最优-原版:  α={b['alpha']:+.2f}%  收益={b['total_r']:+.1f}%  T={b['n_trades']}笔  夏普={b['sharpe']:.2f}  SAME={best_asym_key[0]}/REV={best_asym_key[1]}")
    if best_asym_c_key:
        b = asym_c_results[best_asym_c_key]
        print(f"  新最优-确认:  α={b['alpha']:+.2f}%  收益={b['total_r']:+.1f}%  T={b['n_trades']}笔  夏普={b['sharpe']:.2f}  SAME={best_asym_c_key[0]}/REV={best_asym_c_key[1]}")
    print()

    new_params[name] = {
        'old': {'same': old_s, 'rev': old_r},
        'best_asym': {
            'same': best_asym_key[0], 'rev': best_asym_key[1],
            'metrics': asym_results[best_asym_key]
        } if best_asym_key else None,
        'best_asym_c': {
            'same': best_asym_c_key[0], 'rev': best_asym_c_key[1],
            'metrics': asym_c_results[best_asym_c_key]
        } if best_asym_c_key else None,
        'old_asym_metrics': old_asym,
        'old_asym_c_metrics': old_asym_c,
    }

out = OUTPUT / 'asym_opt_params.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(new_params, f, ensure_ascii=False, indent=2)
print(f"\n参数结果保存: {out}")
