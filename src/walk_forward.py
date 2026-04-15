"""
Walk-Forward 验证
================
思路：
  - 训练窗口（IS）：在该段数据上网格搜索最优参数
  - 测试窗口（OOS）：用训练段找到的参数，在紧接其后的时间段测试
  - 滚动向前，重复

窗口设置（3年数据）：
  训练：18个月  测试：6个月  滚动：3个月
  窗口1: IS 2023-04 ~ 2024-09  OOS 2024-10 ~ 2025-03
  窗口2: IS 2023-07 ~ 2025-00  OOS 2025-01 ~ 2025-06
  窗口3: IS 2023-10 ~ 2025-03  OOS 2025-04 ~ 2025-09
  窗口4: IS 2024-01 ~ 2025-06  OOS 2025-07 ~ 2025-12
  窗口5: IS 2024-04 ~ 2025-09  OOS 2025-10 ~ 2026-03

对比：
  A. WF-OOS：每个窗口用各自IS最优参数在OOS测试 → 拼接的OOS曲线
  B. IS-FIXED：全程用固定IS最优参数（v2）→ 标准回测
  C. BNH：买入持有
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from dateutil.relativedelta import relativedelta
import warnings
warnings.filterwarnings('ignore')

UPLOADS = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/uploads")
OUTPUT  = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")

W_FLAT=0.015; W_SAME=0.90; W_REV=0.45
D_FLAT=0.005; COST_BPS=15
UP=1; DOWN=-1; FLAT=0

# v2 固定参数（样本内优化结果）
V2_PARAMS = {
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

# 网格（与优化脚本一致）
SAME_RANGE = [0.30, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00, 3.50, 4.00, 5.00]
REV_RANGE  = [0.15, 0.30, 0.45, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50]
MIN_TRADES = 2

# Walk-Forward 窗口（IS=18月, OOS=6月, step=3月）
FULL_START = pd.Timestamp("2023-04-17")
FULL_END   = pd.Timestamp("2026-04-15")
IS_MONTHS  = 18
OOS_MONTHS = 6
STEP_MONTHS = 3

def make_windows():
    windows = []
    is_start = FULL_START
    while True:
        is_end   = is_start + relativedelta(months=IS_MONTHS) - pd.Timedelta(days=1)
        oos_start = is_end + pd.Timedelta(days=1)
        oos_end   = oos_start + relativedelta(months=OOS_MONTHS) - pd.Timedelta(days=1)
        if oos_end > FULL_END:
            oos_end = FULL_END
        if oos_start >= FULL_END:
            break
        windows.append({
            'is_start': is_start, 'is_end': is_end,
            'oos_start': oos_start, 'oos_end': oos_end,
            'label': f"IS:{is_start.strftime('%y.%m')}~{is_end.strftime('%y.%m')} | OOS:{oos_start.strftime('%y.%m')}~{oos_end.strftime('%y.%m')}"
        })
        is_start += relativedelta(months=STEP_MONTHS)
    return windows

def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close',
                             '最高':'high','最低':'low'})
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
    d = daily.copy()
    d['wk'] = d['date'].dt.to_period('W')
    def agg_w(g):
        g = g.sort_values('date')
        return pd.Series({'open': g['open'].iloc[0], 'high': g['high'].max(),
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
    return d

def build_dts_asym(d_wp, d_same, d_rev):
    d = d_wp.copy()
    d['ds'] = d.apply(lambda r: classify(r, D_FLAT), axis=1)
    d['da'] = d.apply(amp_pct, axis=1)
    pos = 0; dsigs = [0]
    for i in range(1, len(d)):
        p, c = d.iloc[i-1], d.iloc[i]
        np_, _, _ = seven_rules(p['ds'], c['ds'], p['da'], c['da'], pos, d_same, d_rev)
        dsigs.append(np_); pos = np_
    d['dts'] = dsigs
    d['dts_s'] = d['dts'].shift(1).fillna(0).astype(int)
    asym = []; pos_a = 0; prev_wp = 0
    for i, row in d.iterrows():
        wp = int(row['wp']); dts = int(row['dts_s'])
        if wp == 0: pos_a = 0
        elif prev_wp == 0 and wp == 1: pos_a = 1
        else:
            if pos_a == 1 and dts == 0: pos_a = 0
            elif pos_a == 0 and dts == 1: pos_a = 1
        asym.append(pos_a); prev_wp = wp
    d['pos_asym'] = asym
    return d

def backtest_fast(d, pos_col, start, end, init=1_000_000.0):
    seg = d[(d['date'] >= start) & (d['date'] <= end)].reset_index(drop=True)
    if len(seg) < 5: return None
    cash = init; shares = 0.0; pos = 0; trades = 0; ep = 0.0; equity = []
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
    return {'alpha': round(tr-br,3), 'total_r': round(tr,3), 'bnh_r': round(br,3),
            'n_trades': trades, 'dates': [str(x.date()) for x in seg['date']],
            'cum_ret': ((eq/init-1)*100).round(3).tolist(),
            'bnh_ret': ((bnh/init-1)*100).round(3).tolist(),
            'end_val': round(eq.iloc[-1],2)}

def optimize_is(d_wp, is_start, is_end):
    """在 IS 段上网格搜索最优 SAME/REV"""
    best_alpha = -9999; best_s = 1.0; best_r = 1.0
    for d_same in SAME_RANGE:
        for d_rev in REV_RANGE:
            dsig = build_dts_asym(d_wp, d_same, d_rev)
            r = backtest_fast(dsig, 'pos_asym', is_start, is_end)
            if r and r['n_trades'] >= MIN_TRADES and r['alpha'] > best_alpha:
                best_alpha = r['alpha']; best_s = d_same; best_r = d_rev
    return best_s, best_r, best_alpha

# === 主流程 ===
windows = make_windows()
print(f"Walk-Forward 窗口（IS={IS_MONTHS}月, OOS={OOS_MONTHS}月, step={STEP_MONTHS}月）：")
for i, w in enumerate(windows):
    print(f"  W{i+1}: {w['label']}")
print()

all_results = {}

for name in ETF_FILES:
    v2_s, v2_r = V2_PARAMS[name]
    daily = load_etf(name)
    d_wp = build_weekly_perm(daily)
    print(f"{'─'*60}")
    print(f"{name}  (v2固定参数: SAME={v2_s}/REV={v2_r})")
    print(f"{'─'*60}")

    etf_data = {
        'windows': [],
        'oos_concat': {'wf': [], 'fixed': [], 'bnh': [], 'dates': []},
        'v2_params': {'same': v2_s, 'rev': v2_r},
    }

    for i, w in enumerate(windows):
        # IS 优化
        opt_s, opt_r, is_alpha = optimize_is(d_wp, w['is_start'], w['is_end'])

        # OOS 测试：WF参数（IS最优）
        dsig_wf = build_dts_asym(d_wp, opt_s, opt_r)
        oos_wf = backtest_fast(dsig_wf, 'pos_asym', w['oos_start'], w['oos_end'])

        # OOS 测试：固定v2参数
        dsig_fx = build_dts_asym(d_wp, v2_s, v2_r)
        oos_fx = backtest_fast(dsig_fx, 'pos_asym', w['oos_start'], w['oos_end'])

        if oos_wf and oos_fx:
            etf_data['windows'].append({
                'label': w['label'], 'idx': i+1,
                'is_start': str(w['is_start'].date()), 'is_end': str(w['is_end'].date()),
                'oos_start': str(w['oos_start'].date()), 'oos_end': str(w['oos_end'].date()),
                'opt_same': opt_s, 'opt_rev': opt_r, 'is_best_alpha': round(is_alpha,2),
                'oos_wf':    {'alpha': oos_wf['alpha'], 'total_r': oos_wf['total_r'], 'bnh_r': oos_wf['bnh_r'], 'n_trades': oos_wf['n_trades']},
                'oos_fixed': {'alpha': oos_fx['alpha'], 'total_r': oos_fx['total_r'], 'bnh_r': oos_fx['bnh_r'], 'n_trades': oos_fx['n_trades']},
                'dates_wf': oos_wf['dates'], 'cum_ret_wf': oos_wf['cum_ret'],
                'dates_fx': oos_fx['dates'], 'cum_ret_fx': oos_fx['cum_ret'],
                'bnh_ret': oos_wf['bnh_ret'],
            })
            print(f"  W{i+1} IS最优 SAME={opt_s}/REV={opt_r}(α={is_alpha:+.1f}%)  "
                  f"OOS-WF α={oos_wf['alpha']:+.1f}%  OOS-固定 α={oos_fx['alpha']:+.1f}%  "
                  f"BNH={oos_wf['bnh_r']:+.1f}%")

    # 汇总 OOS Alpha
    wf_alphas = [w['oos_wf']['alpha'] for w in etf_data['windows']]
    fx_alphas = [w['oos_fixed']['alpha'] for w in etf_data['windows']]
    etf_data['summary'] = {
        'wf_mean_alpha': round(np.mean(wf_alphas), 2),
        'fx_mean_alpha': round(np.mean(fx_alphas), 2),
        'wf_win_rate':   round(sum(1 for a in wf_alphas if a > 0)/len(wf_alphas)*100, 1),
        'fx_win_rate':   round(sum(1 for a in fx_alphas if a > 0)/len(fx_alphas)*100, 1),
        'n_windows': len(etf_data['windows']),
    }
    print(f"  → WF-OOS 平均α: {etf_data['summary']['wf_mean_alpha']:+.2f}%  "
          f"胜率{etf_data['summary']['wf_win_rate']}% | "
          f"固定参数OOS 平均α: {etf_data['summary']['fx_mean_alpha']:+.2f}%  "
          f"胜率{etf_data['summary']['fx_win_rate']}%")
    print()

    all_results[name] = etf_data

out = OUTPUT / 'walk_forward_results.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, default=str)
print(f"\n保存: {out}  ({out.stat().st_size//1024} KB)")
