#!/usr/bin/env python3
"""
量价确认版 v2 回测
=============================
对比：
  pos_v2        — 原始静态v2（纯价格）
  pos_v2_vol5   — DTS翻转需量 > MA(10)×0.5  （宽松确认）
  pos_v2_vol8   — DTS翻转需量 > MA(10)×0.8  （标准确认）
  pos_v2_vol10  — DTS翻转需量 > MA(10)×1.0  （严格确认）
  pos_v2_to     — 换手率版：DTS翻转需换手率 > MA(10)×0.8

逻辑：振幅满足阈值 AND 成交量满足确认 → DTS信号才翻转
      否则 DTS 状态维持不变（不触发，等待更有力的信号）
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

VOL_CONFIGS = {
    'v2':          {'vol_ma':10, 'vol_factor':None,  'use_turnover':False},  # 原始，无量确认
    'v2_vol5':     {'vol_ma':10, 'vol_factor':0.5,   'use_turnover':False},
    'v2_vol8':     {'vol_ma':10, 'vol_factor':0.8,   'use_turnover':False},
    'v2_vol10':    {'vol_ma':10, 'vol_factor':1.0,   'use_turnover':False},
    'v2_to8':      {'vol_ma':10, 'vol_factor':0.8,   'use_turnover':True},   # 换手率版
}

def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close',
                             '最高':'high','最低':'low','成交量':'volume','换手率':'turnover'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close','volume','turnover']].sort_values('date').reset_index(drop=True)

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

def compute_wts(d):
    d=d.copy()
    d['wk']=d['date'].dt.to_period('W')
    def agg_w(g):
        g=g.sort_values('date')
        return pd.Series({'open':g['open'].iloc[0],'high':g['high'].max(),
                          'low':g['low'].min(),'close':g['close'].iloc[-1]})
    wk=d.groupby('wk').apply(agg_w).reset_index().dropna()
    wo=wk['open'].values;wh=wk['high'].values;wl=wk['low'].values;wc=wk['close'].values
    wst=[classify(wo[i],wh[i],wl[i],wc[i],W_FLAT) for i in range(len(wk))]
    wam=amp_pct(wo,wh,wl); pos=0; ws=[0]
    for i in range(1,len(wk)):
        pos=seven_rules(wst[i-1],wst[i],wam[i-1],wam[i],pos,W_SAME,W_REV); ws.append(pos)
    wk['wts']=ws
    w2p={str(wk['wk'].iloc[i+1]):wk['wts'].iloc[i] for i in range(len(wk)-1)}
    d['wp']=d['wk'].apply(lambda w:w2p.get(str(w),0))
    return d

def build_all_variants(d, s_thr, r_thr):
    """Build all pos_v2_xxx variants"""
    d=d.copy(); n=len(d)
    o=d['open'].values;h=d['high'].values;l=d['low'].values;c=d['close'].values
    vol=d['volume'].values; to=d['turnover'].values

    # Precompute volume / turnover moving averages
    vol_ma10=pd.Series(vol).rolling(10,min_periods=3).mean().values
    to_ma10=pd.Series(to).rolling(10,min_periods=3).mean().values

    # Daily K-line classification
    ds=[classify(o[i],h[i],l[i],c[i],D_FLAT) for i in range(n)]
    da=amp_pct(o,h,l)

    wp=d['wp'].values

    for cfg_name, cfg in VOL_CONFIGS.items():
        vol_factor = cfg['vol_factor']
        use_to     = cfg['use_turnover']
        vol_ma_arr = to_ma10 if use_to else vol_ma10
        raw_arr    = to if use_to else vol

        # ─── DTS with optional volume confirmation ───
        pos=0; dts=np.empty(n,dtype=int)
        for i in range(n):
            if i==0: dts[i]=0; continue
            # What would the rule say?
            new_pos = seven_rules(ds[i-1],ds[i],da[i-1],da[i],pos,s_thr,r_thr)
            # Volume confirmation: only allow state change if volume is sufficient
            if vol_factor is not None and new_pos != pos:
                vol_ok = (vol_ma_arr[i]>0) and (raw_arr[i] >= vol_ma_arr[i] * vol_factor)
                if not vol_ok:
                    new_pos = pos  # Block the state change — hold current DTS
            dts[i]=new_pos; pos=new_pos

        dts_s=np.empty(n,dtype=int); dts_s[0]=0; dts_s[1:]=dts[:-1]

        # Asymmetric confirmed-entry strategy
        pos_c=0; prev_w=0; ac=[]
        for i in range(n):
            w=int(wp[i]); dt=int(dts_s[i])
            if w==0: pos_c=0
            elif prev_w==0 and w==1:
                if dt==1: pos_c=1
            else:
                if pos_c==1 and dt==0: pos_c=0
                elif pos_c==0 and dt==1: pos_c=1
            ac.append(pos_c); prev_w=w

        d[f'pos_{cfg_name}']=ac

        # Count how many DTS state changes were blocked by volume filter
        if vol_factor is not None:
            blocked = sum(1 for i in range(1,n) if
                seven_rules(ds[i-1],ds[i],da[i-1],da[i],dts[i-1],s_thr,r_thr) != dts[i])
            # (this counts positions held instead of flipped)

    return d

def backtest(d_full, pos_col, start, end, init=1_000_000.0):
    d=d_full[(d_full['date']>=start)&(d_full['date']<=end)].copy().reset_index(drop=True)
    if len(d)<5: return None
    opens=d['open'].values; closes=d['close'].values; pos_arr=d[pos_col].values
    cash=init; shares=0.0; prev=0; ep=0.0; ed=None; equity=[]; trades=[]
    for i in range(len(d)):
        np_=int(pos_arr[i]); o=opens[i]; c=closes[i]
        if np_!=prev:
            if prev==1 and shares>0:
                cash=shares*o*(1-COST_BPS/10000)
                pnl=(o*(1-COST_BPS/10000)-ep)/ep*100
                trades.append({'entry_date':str(ed.date()),'exit_date':str(d['date'].iloc[i].date()),
                    'pnl_pct':round(pnl,2),'hold_days':(d['date'].iloc[i]-ed).days}); shares=0.0
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
    one_day=[t for t in trades if t['hold_days']<=1]
    return {
        'dates':[str(x.date()) for x in d['date']],
        'equity':eq.round(2).tolist(),'bnh':bnh.round(2).tolist(),
        'cum_ret':((eq/init-1)*100).round(2).tolist(),'bnh_ret':((bnh/init-1)*100).round(2).tolist(),
        'metrics':{
            'total_return':round(tr,2),'bnh_return':round(br,2),'alpha':round(tr-br,2),
            'sharpe':round(sh,2),'max_drawdown':round(mdd,2),
            'win_rate':round(len(wins)/len(trades)*100,1) if trades else 0,
            'n_trades':len(trades),'long_pct':round((pos_arr==1).sum()/n2*100,1),
            'one_day_trades':len(one_day),
            'one_day_pct':round(len(one_day)/len(trades)*100,1) if trades else 0,
        }
    }

# ─── Main ─────────────────────────────────────────────────
COLS = ['pos_v2','pos_v2_vol5','pos_v2_vol8','pos_v2_vol10','pos_v2_to8']
LABELS = {
    'pos_v2':       '原始v2（无量确认）',
    'pos_v2_vol5':  '量×0.5确认（宽松）',
    'pos_v2_vol8':  '量×0.8确认（标准）',
    'pos_v2_vol10': '量×1.0确认（严格）',
    'pos_v2_to8':   '换手率×0.8确认',
}

all_data={}
print(f"\n{'标的':10s}  {'阶段':5s}  {'原v2':>14s}  {'量×0.5':>14s}  {'量×0.8':>14s}  {'量×1.0':>14s}  {'换手×0.8':>14s}  BNH")
print('─'*105)

for name in ETF_FILES:
    d=load_etf(name)
    d=d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)
    s,r=STATIC_PARAMS[name]
    d=compute_wts(d)
    d=build_all_variants(d,s,r)

    etf={'name':name,'phases':{}}
    for plbl,ps,pe in PHASES:
        phase={}
        for col in COLS:
            res=backtest(d,col,ps,pe)
            if res: phase[col]={**res,'label':LABELS[col]}
        etf['phases'][plbl]=phase
    all_data[name]=etf

    for plbl,ps,pe in PHASES:
        ph=etf['phases'][plbl]
        bnh=ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return',0)
        vals=[ph.get(c,{}).get('metrics',{}) for c in COLS]
        best_a=max((v.get('alpha',-999) for v in vals if v),default=0)
        row=f"{name:10s}  {plbl:5s}  "
        for m in vals:
            if m:
                mk='★' if abs(m.get('alpha',0)-best_a)<0.1 else ' '
                row+=f"{mk}{m['total_return']:+5.1f}%(α{m['alpha']:+.1f})  "
        print(row+f"BNH:{bnh:+.1f}%")

    # Show trade count comparison for full period
    ph_full=etf['phases']['全期']
    print(f"  交易统计:")
    for col in COLS:
        m=ph_full.get(col,{}).get('metrics',{})
        if m:
            print(f"    {LABELS[col]:18s}  交易{m['n_trades']:3d}笔  1日内:{m['one_day_pct']:4.1f}%  胜率:{m['win_rate']:5.1f}%")
    print()

out=OUTPUT/'volume_confirm_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data,f,ensure_ascii=False,default=str)
print(f"保存: {out}")
