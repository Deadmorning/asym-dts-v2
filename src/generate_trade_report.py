"""
生成每笔交易明细 CSV + 回测汇总报告
输出到 results/ 目录
"""
import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

UPLOADS = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/uploads")
RESULTS = Path(__file__).parent.parent / 'results'
RESULTS.mkdir(exist_ok=True)

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
PERIODS = [
    ("全程", "2023-04-17", "2026-04-15"),
    ("熊市", "2023-04-17", "2024-09-20"),
    ("牛市", "2024-09-23", "2026-04-15"),
]

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

def build_signals(daily, new_s, new_r):
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
            if pos_a == 1 and dts == 0: pos_a = 0
            elif pos_a == 0 and dts == 1: pos_a = 1
        asym.append(pos_a); prev_wp = wp
    d['pos_asym'] = asym
    return d

def backtest_with_trades(d, pos_col, start, end, init=1_000_000.0):
    seg = d[(d['date'] >= start) & (d['date'] <= end)].copy().reset_index(drop=True)
    if len(seg) < 5: return None, []
    cash = init; shares = 0.0; pos = 0; trades = []; ep = 0.0; ed = None; equity = []
    for i, row in seg.iterrows():
        np_ = int(row[pos_col]); o = row['open']; c = row['close']
        if np_ != pos:
            if pos == 1 and shares > 0:
                sell_price = o * (1 - COST_BPS/10000)
                cash = shares * sell_price
                pnl = (sell_price - ep) / ep * 100
                trades.append({
                    '入场日期': str(ed.date()), '出场日期': str(row['date'].date()),
                    '入场价格': round(ep, 4), '出场价格': round(o, 4),
                    '含费入场': round(ep, 4), '含费出场': round(sell_price, 4),
                    '持有天数': (row['date']-ed).days,
                    '盈亏%': round(pnl, 3),
                    '胜败': '盈' if pnl > 0 else '亏'
                })
                shares = 0.0
            if np_ == 1:
                buy_price = o * (1 + COST_BPS/10000)
                shares = (cash / buy_price); cash = 0.0
                ep = buy_price; ed = row['date']
        pos = np_; equity.append(cash + shares * c)
    if pos == 1 and shares > 0:
        last = seg.iloc[-1]
        sell_price = last['close'] * (1 - COST_BPS/10000)
        pnl = (sell_price - ep) / ep * 100
        trades.append({
            '入场日期': str(ed.date()), '出场日期': str(last['date'].date()),
            '入场价格': round(ep, 4), '出场价格': round(last['close'], 4),
            '含费入场': round(ep, 4), '含费出场': round(sell_price, 4),
            '持有天数': (last['date']-ed).days,
            '盈亏%': round(pnl, 3),
            '胜败': '盈（持仓中）' if pnl > 0 else '亏（持仓中）'
        })
    eq = pd.Series(equity)
    bnh = init * seg['close'] / seg['close'].iloc[0]
    tr = (eq.iloc[-1]/init-1)*100; br = (bnh.iloc[-1]/init-1)*100
    dr = eq.pct_change().dropna()
    sh = dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd = ((eq-eq.cummax())/eq.cummax()).min()*100
    wins = [t for t in trades if '盈' in t['胜败']]
    summary = {
        '标的': '', '阶段': '', '参数SAME': 0, '参数REV': 0,
        '总收益%': round(tr, 2), 'BNH收益%': round(br, 2), '超额Alpha%': round(tr-br, 2),
        '夏普比率': round(sh, 2), '最大回撤%': round(mdd, 2),
        '交易笔数': len(trades), '胜率%': round(len(wins)/len(trades)*100, 1) if trades else 0,
        '平均持有天数': round(sum(t['持有天数'] for t in trades)/len(trades), 1) if trades else 0,
        '持多比例%': round((seg[pos_col]==1).sum()/len(seg)*100, 1),
        '起始日': str(seg['date'].iloc[0].date()), '结束日': str(seg['date'].iloc[-1].date()),
    }
    return summary, trades

# === 主流程 ===
all_trades = []
all_summaries = []

for name in ETF_FILES:
    new_s, new_r = NEW_PARAMS[name]
    daily = load_etf(name)
    dsig = build_signals(daily, new_s, new_r)
    print(f"处理 {name}...")
    for plabel, ps, pe in PERIODS:
        summary, trades = backtest_with_trades(dsig, 'pos_asym', ps, pe)
        if summary:
            summary['标的'] = name
            summary['阶段'] = plabel
            summary['参数SAME'] = new_s
            summary['参数REV'] = new_r
            all_summaries.append(summary)
            for i, t in enumerate(trades, 1):
                all_trades.append({'标的': name, '阶段': plabel, '交易序号': i, **t})

# 输出 CSV
summary_df = pd.DataFrame(all_summaries)
summary_df.to_csv(RESULTS/'backtest_summary.csv', index=False, encoding='utf-8-sig')
print(f"回测汇总: {RESULTS/'backtest_summary.csv'}  ({len(summary_df)} 行)")

trades_df = pd.DataFrame(all_trades)
trades_df.to_csv(RESULTS/'all_trades.csv', index=False, encoding='utf-8-sig')
print(f"交易明细: {RESULTS/'all_trades.csv'}  ({len(trades_df)} 笔)")

# 按 ETF 分文件输出
for name in ETF_FILES:
    sub = trades_df[(trades_df['标的']==name) & (trades_df['阶段']=='全程')]
    if not sub.empty:
        fname = RESULTS/f"trades_{name.replace('ETF','').strip()}_全程.csv"
        sub.to_csv(fname, index=False, encoding='utf-8-sig')
        print(f"  {name} 全程: {len(sub)} 笔 → {fname.name}")

print("\n完成！")
