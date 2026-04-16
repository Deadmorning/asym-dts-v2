#!/usr/bin/env python3
"""
双层量价架构回测
=====================================
方式一：双层独立量确认
  WTS 翻转 + 周量 > 周均量×factor → 有效
  DTS 翻转 + 日量 > 日均量×factor → 有效

方式二：量决定仓位大小
  强WTS+强DTS   → 满仓 1.0
  弱WTS或弱DTS  → 半仓 0.5
  弱WTS且弱DTS  → 轻仓 0.25（可选跳过）

对比基准：原始v2（纯价格）
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings; warnings.filterwarnings('ignore')

UPLOADS = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/uploads")
OUTPUT  = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")

W_FLAT=0.015; W_SAME=0.90; W_REV=0.45
D_FLAT=0.005; COST_BPS=15
UP=1; DOWN=-1; FLAT=0
VOL_MA = 10   # volume MA period (days and weeks)
VOL_F  = 0.8  # volume factor threshold

STATIC_PARAMS = {
    "上证50ETF":  (1.50, 2.50), "沪深300ETF": (2.50, 2.50),
    "中证500ETF": (2.50, 2.50), "科创50ETF":  (2.50, 1.50),
    "深证100ETF": (3.00, 2.00), "创业板ETF":  (4.00, 1.00),
}
ETF_FILES = {
    "上证50ETF":  "510050_上证_50ETF.csv",  "沪深300ETF": "510300_沪深_300ETF.csv",
    "中证500ETF": "510500_中证_500ETF.csv",  "科创50ETF":  "588080_科创_50ETF.csv",
    "深证100ETF": "159901_深证_100ETF.csv",  "创业板ETF":  "159915_创业板_ETF.csv",
}
FULL_START='2023-04-17'; FULL_END='2026-04-15'
PHASES=[("熊市","2023-04-17","2024-09-19"),("牛市","2024-09-20","2026-04-15"),("全期","2023-04-17","2026-04-15")]

def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close',
                             '最高':'high','最低':'low','成交量':'volume'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close','volume']].sort_values('date').reset_index(drop=True)

def classify(o,h,l,c,thr): return FLAT if (h-l)/o<thr else (UP if c>=o else DOWN)
def amp_pct(o,h,l): return (h-l)/o*100.0

def seven_rules(dp,dc,ap,ac,prev,st,rt):
    raw=None
    if dp==UP and dc==UP: raw=1
    elif dp==DOWN and dc==DOWN: raw=-1
    elif dp==UP and dc==DOWN: raw=-1
    elif dp==DOWN and dc==UP: raw=1
    elif (dp==FLAT or dp==UP) and (dc==UP or dc==FLAT): return 1
    elif (dp==FLAT or dp==DOWN) and (dc==DOWN or dc==FLAT): return 0
    elif dp==FLAT and dc==FLAT: return prev
    else: return prev
    diff=abs(ac-ap); thr2=st if (dp>0)==(dc>0) else rt
    if diff<thr2: return prev
    return max(raw,0)

def build_signals(d, s_thr, r_thr):
    d = d.copy(); n = len(d)
    o=d['open'].values; h=d['high'].values; l=d['low'].values
    c=d['close'].values; vol=d['volume'].values

    # ── Daily volume MA ──────────────────────────────────
    d_vol_ma = pd.Series(vol).rolling(VOL_MA, min_periods=3).mean().values
    d_vol_strong = (vol >= d_vol_ma * VOL_F)  # bool array

    # ── Weekly aggregation ───────────────────────────────
    d['wk'] = d['date'].dt.to_period('W')
    def agg_w(g):
        g = g.sort_values('date')
        return pd.Series({
            'open':  g['open'].iloc[0],  'high':  g['high'].max(),
            'low':   g['low'].min(),      'close': g['close'].iloc[-1],
            'vol':   g['volume'].sum()
        })
    wk = d.groupby('wk').apply(agg_w).reset_index().dropna()
    wk_vol = wk['vol'].values
    wk_vol_ma = pd.Series(wk_vol).rolling(VOL_MA, min_periods=3).mean().values
    wk_vol_strong = (wk_vol >= wk_vol_ma * VOL_F)  # bool array per week

    # Map weekly vol_strong back to daily rows
    wk_list = wk['wk'].tolist()
    wk_vs_dict = {str(wk_list[i]): bool(wk_vol_strong[i]) for i in range(len(wk_list))}
    d['wk_vol_strong'] = d['wk'].apply(lambda w: wk_vs_dict.get(str(w), True))

    # ── WTS (pure price, no vol) ─────────────────────────
    wo=wk['open'].values; wh=wk['high'].values; wl=wk['low'].values; wc=wk['close'].values
    wst = [classify(wo[i],wh[i],wl[i],wc[i],W_FLAT) for i in range(len(wk))]
    wam = amp_pct(wo, wh, wl)

    # WTS without volume filter (baseline)
    pos=0; ws_pure=[0]
    for i in range(1, len(wk)):
        pos = seven_rules(wst[i-1],wst[i],wam[i-1],wam[i],pos,W_SAME,W_REV)
        ws_pure.append(pos)

    # WTS with volume filter (state change blocked if week volume is weak)
    pos=0; ws_vol=[0]
    for i in range(1, len(wk)):
        new_pos = seven_rules(wst[i-1],wst[i],wam[i-1],wam[i],pos,W_SAME,W_REV)
        if new_pos != pos and not wk_vol_strong[i]:
            new_pos = pos  # Block WTS flip on low-volume week
        ws_vol.append(new_pos); pos=new_pos

    # Map WTS signals to daily (shifted by 1 week → next week's signal)
    w2p_pure = {str(wk_list[i+1]): ws_pure[i] for i in range(len(wk_list)-1)}
    w2p_vol  = {str(wk_list[i+1]): ws_vol[i]  for i in range(len(wk_list)-1)}
    d['wp']      = d['wk'].apply(lambda w: w2p_pure.get(str(w),0))
    d['wp_vol']  = d['wk'].apply(lambda w: w2p_vol.get(str(w),0))

    # Also store weekly vol strength for next week (shifted)
    wk_vs_next = {str(wk_list[i+1]): bool(wk_vol_strong[i]) for i in range(len(wk_list)-1)}
    d['wk_vol_prev'] = d['wk'].apply(lambda w: wk_vs_next.get(str(w), True))

    # ── DTS ─────────────────────────────────────────────
    ds = [classify(o[i],h[i],l[i],c[i],D_FLAT) for i in range(n)]
    da = amp_pct(o,h,l)

    # DTS pure (no vol)
    pos=0; dts_pure=np.empty(n,dtype=int)
    for i in range(n):
        if i==0: dts_pure[i]=0; continue
        pos = seven_rules(ds[i-1],ds[i],da[i-1],da[i],pos,s_thr,r_thr)
        dts_pure[i]=pos

    # DTS with volume filter
    pos=0; dts_vol=np.empty(n,dtype=int)
    for i in range(n):
        if i==0: dts_vol[i]=0; continue
        new_pos = seven_rules(ds[i-1],ds[i],da[i-1],da[i],pos,s_thr,r_thr)
        if new_pos != pos and not d_vol_strong[i]:
            new_pos = pos
        dts_vol[i]=new_pos; pos=new_pos

    # Shift DTS by 1 day (signal → next day's open)
    dts_s_pure = np.empty(n,dtype=int); dts_s_pure[0]=0; dts_s_pure[1:]=dts_pure[:-1]
    dts_s_vol  = np.empty(n,dtype=int); dts_s_vol[0]=0;  dts_s_vol[1:]=dts_vol[:-1]

    # ── Strategy variants ────────────────────────────────
    wp_pure  = d['wp'].values
    wp_volf  = d['wp_vol'].values
    dvs      = d_vol_strong  # daily vol strong array
    wvs      = d['wk_vol_prev'].values  # previous week vol strong

    def make_asym_c(wp_arr, dts_s_arr):
        """Asymmetric confirmed-entry, binary 0/1"""
        pos_c=0; prev_w=0; ac=[]
        for i in range(n):
            w=int(wp_arr[i]); dt=int(dts_s_arr[i])
            if w==0: pos_c=0
            elif prev_w==0 and w==1:
                if dt==1: pos_c=1
            else:
                if pos_c==1 and dt==0: pos_c=0
                elif pos_c==0 and dt==1: pos_c=1
            ac.append(pos_c); prev_w=w
        return np.array(ac)

    # A. Original v2 (pure price)
    d['pos_v2'] = make_asym_c(wp_pure, dts_s_pure)

    # B. 方式一a: DTS vol only (already tested, add for comparison)
    d['pos_dts_vol'] = make_asym_c(wp_pure, dts_s_vol)

    # C. 方式一b: WTS vol only
    d['pos_wts_vol'] = make_asym_c(wp_volf, dts_s_pure)

    # D. 方式一c: BOTH layers vol confirmed (strictest)
    d['pos_both_vol'] = make_asym_c(wp_volf, dts_s_vol)

    # E. 方式二: Volume-based position sizing
    # Use original wp + dts_s_pure, but size based on vol strength at each layer
    # vol_score: 0=none, 1=one layer strong, 2=both strong
    # position: 2→1.0, 1→0.5, 0→0.25
    base_pos = make_asym_c(wp_pure, dts_s_pure)  # same entry/exit logic
    sized_pos = np.zeros(n)
    for i in range(n):
        if base_pos[i] == 1:
            w_strong = bool(wvs[i])
            d_strong = bool(dvs[i])
            score = int(w_strong) + int(d_strong)
            if score == 2:   sized_pos[i] = 1.0
            elif score == 1: sized_pos[i] = 0.5
            else:            sized_pos[i] = 0.25
        else:
            sized_pos[i] = 0.0
    d['pos_sized'] = sized_pos  # float position

    return d

def backtest_binary(d_full, pos_col, start, end, init=1_000_000.0):
    """Standard backtest for binary (0/1) position."""
    d=d_full[(d_full['date']>=start)&(d_full['date']<=end)].copy().reset_index(drop=True)
    if len(d)<5: return None
    pos_arr=d[pos_col].values.astype(int)
    opens=d['open'].values; closes=d['close'].values
    cash=init; shares=0.0; prev=0; ep=0.0; ed=None; equity=[]; trades=[]
    for i in range(len(d)):
        np_=pos_arr[i]; o=opens[i]; c=closes[i]
        if np_!=prev:
            if prev==1 and shares>0:
                cash=shares*o*(1-COST_BPS/10000)
                pnl=(o*(1-COST_BPS/10000)-ep)/ep*100
                trades.append({'pnl_pct':round(pnl,2),'hold_days':(d['date'].iloc[i]-ed).days}); shares=0.0
            if np_==1:
                shares=cash*(1-COST_BPS/10000)/o; cash=0.0
                ep=o*(1+COST_BPS/10000); ed=d['date'].iloc[i]
        prev=np_; equity.append(cash+shares*c)
    if prev==1 and shares>0:
        last=d.iloc[-1]; pnl=(last['close']*(1-COST_BPS/10000)-ep)/ep*100
        trades.append({'pnl_pct':round(pnl,2),'hold_days':(last['date']-ed).days})
    eq=pd.Series(equity); bnh=init*d['close']/d['close'].iloc[0]; n2=len(eq)
    tr=(eq.iloc[-1]/init-1)*100; br=(bnh.iloc[-1]/init-1)*100
    dr=eq.pct_change().dropna(); sh=dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    wins=[t for t in trades if t['pnl_pct']>0]
    return {
        'dates':[str(x.date()) for x in d['date']],
        'equity':eq.round(2).tolist(),'bnh':bnh.round(2).tolist(),
        'cum_ret':((eq/init-1)*100).round(2).tolist(),'bnh_ret':((bnh/init-1)*100).round(2).tolist(),
        'metrics':{
            'total_return':round(tr,2),'bnh_return':round(br,2),'alpha':round(tr-br,2),
            'sharpe':round(sh,2),'max_drawdown':round(mdd,2),
            'win_rate':round(len(wins)/len(trades)*100,1) if trades else 0,
            'n_trades':len(trades),
            'long_pct':round((pos_arr==1).sum()/n2*100,1),
        }
    }

def backtest_sized(d_full, pos_col, start, end, init=1_000_000.0):
    """Backtest for fractional (0/0.25/0.5/1.0) position."""
    d=d_full[(d_full['date']>=start)&(d_full['date']<=end)].copy().reset_index(drop=True)
    if len(d)<5: return None
    pos_arr=d[pos_col].values  # float
    opens=d['open'].values; closes=d['close'].values
    cash=init; shares=0.0; prev_p=0.0; ep=0.0; ed=None; equity=[]; trades=[]
    for i in range(len(d)):
        tgt=pos_arr[i]; o=opens[i]; c=closes[i]
        if abs(tgt-prev_p)>0.01:  # position change
            total = cash + shares*o
            # Close existing if reducing
            if shares>0 and tgt < prev_p:
                sell_shares = shares * (prev_p - tgt) / prev_p if prev_p>0 else shares
                cash += sell_shares * o * (1-COST_BPS/10000)
                shares -= sell_shares
                if tgt==0 and trades:
                    pnl=(o*(1-COST_BPS/10000)-ep)/ep*100 if ep>0 else 0
                    trades[-1]['pnl_pct']=round(pnl,2)
            # Buy if increasing
            if tgt > prev_p:
                buy_value = total * (tgt - prev_p) * (1-COST_BPS/10000)
                new_shares = buy_value / o
                shares += new_shares; cash -= buy_value / (1-COST_BPS/10000)
                ep = total * tgt / shares if shares>0 else o
                if ed is None: ed=d['date'].iloc[i]
                trades.append({'hold_days':0,'pnl_pct':0})
            if tgt==0: ed=None; ep=0
            prev_p=tgt
        equity.append(cash + shares*c)
    eq=pd.Series(equity); bnh=init*d['close']/d['close'].iloc[0]; n2=len(eq)
    tr=(eq.iloc[-1]/init-1)*100; br=(bnh.iloc[-1]/init-1)*100
    dr=eq.pct_change().dropna(); sh=dr.mean()/dr.std()*np.sqrt(252) if dr.std()>0 else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    avg_pos=round(pos_arr.mean()*100,1)
    return {
        'dates':[str(x.date()) for x in d['date']],
        'equity':eq.round(2).tolist(),'bnh':bnh.round(2).tolist(),
        'cum_ret':((eq/init-1)*100).round(2).tolist(),'bnh_ret':((bnh/init-1)*100).round(2).tolist(),
        'metrics':{
            'total_return':round(tr,2),'bnh_return':round(br,2),'alpha':round(tr-br,2),
            'sharpe':round(sh,2),'max_drawdown':round(mdd,2),
            'win_rate':0,'n_trades':len(trades),
            'long_pct':avg_pos,
        }
    }

# ─── Main ──────────────────────────────────────────────────
BINARY_COLS = ['pos_v2','pos_dts_vol','pos_wts_vol','pos_both_vol']
LABELS = {
    'pos_v2':       '原始v2（无量）',
    'pos_dts_vol':  '日线量确认',
    'pos_wts_vol':  '周线量确认',
    'pos_both_vol': '双层量确认',
    'pos_sized':    '量化仓位(0.25~1.0)',
}
COLORS = {
    'pos_v2':       '#1a73e8',
    'pos_dts_vol':  '#f57c00',
    'pos_wts_vol':  '#43a047',
    'pos_both_vol': '#e53935',
    'pos_sized':    '#ab47bc',
}

all_data={}
print(f"\n{'标的':10s}  {'阶段':5s}  {'原v2':>14s}  {'日线量':>14s}  {'周线量':>14s}  {'双层量':>14s}  {'量化仓位':>14s}  BNH")
print('─'*115)

for name in ETF_FILES:
    d=load_etf(name)
    d=d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)
    s,r=STATIC_PARAMS[name]
    d=build_signals(d,s,r)

    etf={'name':name,'phases':{}}
    for plbl,ps,pe in PHASES:
        phase={}
        for col in BINARY_COLS:
            res=backtest_binary(d,col,ps,pe)
            if res: phase[col]={**res,'label':LABELS[col],'color':COLORS[col]}
        res_s=backtest_sized(d,'pos_sized',ps,pe)
        if res_s: phase['pos_sized']={**res_s,'label':LABELS['pos_sized'],'color':COLORS['pos_sized']}
        etf['phases'][plbl]=phase
    all_data[name]=etf

    for plbl,ps,pe in PHASES:
        ph=etf['phases'][plbl]
        bnh=ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return',0)
        all_cols=BINARY_COLS+['pos_sized']
        vals=[ph.get(c,{}).get('metrics',{}) for c in all_cols]
        best_a=max((v.get('alpha',-999) for v in vals if v),default=0)
        row=f"{name:10s}  {plbl:5s}  "
        for m in vals:
            if m:
                mk='★' if abs(m.get('alpha',0)-best_a)<0.15 else ' '
                row+=f"{mk}{m['total_return']:+5.1f}%(α{m['alpha']:+.1f})  "
        print(row+f"BNH:{bnh:+.1f}%")
    print()

out=OUTPUT/'dual_volume_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data,f,ensure_ascii=False,default=str)
print(f"保存: {out}")
