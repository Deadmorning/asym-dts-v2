#!/usr/bin/env python3
"""
扩展对比 Round 3：补测三个被遗漏的基础策略
  - 双RSI：周RSI>50（趋势过滤）+ 日RSI>50（持仓触发）
  - KDJ：K线金叉死叉 + 周线趋势过滤
  - 布林带趋势版：突破上轨入场，跌破中轨（MA）离场
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

def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

# ─── v2 (static) ─────────────────────────────────────────
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

def build_v2(d, s_thr, r_thr):
    d=d.copy(); n=len(d)
    o=d['open'].values;h=d['high'].values;l=d['low'].values;c=d['close'].values
    d['wk']=d['date'].dt.to_period('W')
    def agg_w(g):
        g=g.sort_values('date')
        return pd.Series({'open':g['open'].iloc[0],'high':g['high'].max(),'low':g['low'].min(),'close':g['close'].iloc[-1]})
    wk=d.groupby('wk').apply(agg_w).reset_index().dropna()
    wo=wk['open'].values;wh=wk['high'].values;wl=wk['low'].values;wc=wk['close'].values
    wst=[classify(wo[i],wh[i],wl[i],wc[i],W_FLAT) for i in range(len(wk))]
    wam=amp_pct(wo,wh,wl); pos=0; ws=[0]
    for i in range(1,len(wk)):
        pos=seven_rules(wst[i-1],wst[i],wam[i-1],wam[i],pos,W_SAME,W_REV); ws.append(pos)
    wk['wts']=ws
    w2p={str(wk['wk'].iloc[i+1]):wk['wts'].iloc[i] for i in range(len(wk)-1)}
    d['wp']=d['wk'].apply(lambda w:w2p.get(str(w),0))
    ds=[classify(o[i],h[i],l[i],c[i],D_FLAT) for i in range(n)]
    da=amp_pct(o,h,l); pos=0; dts=np.empty(n,dtype=int)
    for i in range(n):
        if i==0: dts[i]=0; continue
        pos=seven_rules(ds[i-1],ds[i],da[i-1],da[i],pos,s_thr,r_thr); dts[i]=pos
    dts_s=np.empty(n,dtype=int); dts_s[0]=0; dts_s[1:]=dts[:-1]
    wp=d['wp'].values; pos_c=0; prev_w=0; ac=[]
    for i in range(n):
        w=int(wp[i]); dt=int(dts_s[i])
        if w==0: pos_c=0
        elif prev_w==0 and w==1:
            if dt==1: pos_c=1
        else:
            if pos_c==1 and dt==0: pos_c=0
            elif pos_c==0 and dt==1: pos_c=1
        ac.append(pos_c); prev_w=w
    d['pos_v2']=ac
    return d

# ─── RSI helper ──────────────────────────────────────────
def rsi(series, period=14):
    delta=series.diff()
    gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    avg_gain=gain.ewm(alpha=1/period,min_periods=period,adjust=False).mean()
    avg_loss=loss.ewm(alpha=1/period,min_periods=period,adjust=False).mean()
    rs=avg_gain/(avg_loss+1e-10)
    return 100-100/(1+rs)

# ─── 双RSI ───────────────────────────────────────────────
def build_dual_rsi(d, w_period=14, d_period=14, threshold=50):
    """
    周线RSI > threshold → 趋势多头（类WTS）
    日线RSI > threshold → 当日持仓（类DTS）
    两者同时成立 → 持多
    """
    d=d.copy()
    # 周线RSI
    d['wk']=d['date'].dt.to_period('W')
    wk_close=d.groupby('wk')['close'].last()
    wrsi=rsi(wk_close,w_period)
    wrsi_bull=(wrsi>threshold).astype(int).shift(1).fillna(0)  # 前一周信号
    d['wrsi_bull']=d['wk'].map(wrsi_bull).fillna(0).astype(int)
    # 日线RSI
    drsi=rsi(d['close'],d_period)
    drsi_bull=(drsi>threshold).astype(int)
    # 信号：前一日确认（避免look-ahead）
    sig=(d['wrsi_bull'] & drsi_bull.shift(1).fillna(0).astype(int)).astype(int)
    d['pos_dual_rsi']=sig
    return d

# ─── KDJ ────────────────────────────────────────────────
def build_kdj(d, n=9, m1=3, m2=3, w_period=20):
    """
    KDJ (9,3,3) 标准版 + 周线MA过滤
    K线金叉D线（K从下穿上D）→ 买入
    K线死叉D线（K从上穿下D）→ 卖出
    周线MA20过滤：收盘>周MA20才允许入场
    """
    d=d.copy()
    # 计算KDJ
    h=d['high']; l=d['low']; c=d['close']
    low_n=l.rolling(n).min(); high_n=h.rolling(n).max()
    rsv=(c-low_n)/(high_n-low_n+1e-9)*100
    K=rsv.ewm(alpha=1/m1,adjust=False).mean()
    D=K.ewm(alpha=1/m2,adjust=False).mean()
    J=3*K-2*D
    # 金叉：K上穿D
    cross_up=((K>D)&(K.shift(1)<=D.shift(1))).astype(int)
    # 死叉：K下穿D
    cross_dn=((K<D)&(K.shift(1)>=D.shift(1))).astype(int)
    # 周线MA20过滤
    d['wk']=d['date'].dt.to_period('W')
    wk_close=d.groupby('wk')['close'].last()
    wk_ma=wk_close.rolling(w_period).mean()
    wk_bull=(wk_close>wk_ma).astype(int).shift(1).fillna(0)
    d['wk_bull']=d['wk'].map(wk_bull).fillna(0).astype(int)
    # 状态机：金叉进，死叉出，周线不在多头时平仓
    pos=0; signals=[]; wk_b=d['wk_bull'].values
    cu=cross_up.fillna(0).values; cd=cross_dn.fillna(0).values
    for i in range(len(d)):
        if wk_b[i]==0: pos=0
        elif cu[i]==1 and pos==0: pos=1
        elif cd[i]==1 and pos==1: pos=0
        signals.append(pos)
    # shift(1): 信号用前一日，今日开盘执行
    d['pos_kdj']=pd.Series(signals).shift(1).fillna(0).astype(int).values
    return d

# ─── 布林带趋势版 ────────────────────────────────────────
def build_boll_trend(d, period=20, std_mult=2.0, w_period=20):
    """
    布林带趋势跟踪版：
    入场：收盘突破上轨（布林上轨）→ 确认趋势启动
    离场：收盘跌破中轨（MA20）→ 趋势减弱退出
    周线MA20过滤：防止熊市中参与反弹
    """
    d=d.copy()
    c=d['close']
    ma=c.rolling(period).mean()
    std=c.rolling(period).std()
    upper=ma+std_mult*std
    # 突破上轨（收盘>上轨）→ 进场信号
    breakout=(c>upper).astype(int)
    # 跌破中轨（收盘<MA）→ 退出信号
    below_ma=(c<ma).astype(int)
    # 周线MA过滤
    d['wk']=d['date'].dt.to_period('W')
    wk_close=d.groupby('wk')['close'].last()
    wk_ma=wk_close.rolling(w_period).mean()
    wk_bull=(wk_close>wk_ma).astype(int).shift(1).fillna(0)
    d['wk_bull_boll']=d['wk'].map(wk_bull).fillna(0).astype(int)
    # 状态机
    pos=0; signals=[]; wkb=d['wk_bull_boll'].values
    bk=breakout.fillna(0).values; bm=below_ma.fillna(0).values
    for i in range(len(d)):
        if wkb[i]==0: pos=0
        elif bk[i]==1 and pos==0: pos=1
        elif bm[i]==1 and pos==1: pos=0
        signals.append(pos)
    d['pos_boll']=pd.Series(signals).shift(1).fillna(0).astype(int).values
    return d

# ─── Backtest ────────────────────────────────────────────
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
                    'entry_price':round(ep,4),'exit_price':round(o,4),
                    'pnl_pct':round(pnl,2),'hold_days':(d['date'].iloc[i]-ed).days}); shares=0.0
            if np_==1:
                shares=cash*(1-COST_BPS/10000)/o; cash=0.0
                ep=o*(1+COST_BPS/10000); ed=d['date'].iloc[i]
        prev=np_; equity.append(cash+shares*c)
    if prev==1 and shares>0:
        last=d.iloc[-1]; pnl=(last['close']*(1-COST_BPS/10000)-ep)/ep*100
        trades.append({'entry_date':str(ed.date()),'exit_date':str(last['date'].date()),
            'entry_price':round(ep,4),'exit_price':round(last['close'],4),
            'pnl_pct':round(pnl,2),'hold_days':(last['date']-ed).days})
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
            'n_trades':len(trades),'long_pct':round((pos_arr==1).sum()/n2*100,1),
        }
    }

# ─── Main ────────────────────────────────────────────────
STRATS=['pos_v2','pos_dual_rsi','pos_kdj','pos_boll']
LABELS={'pos_v2':'静态v2','pos_dual_rsi':'双RSI(14,50)','pos_kdj':'KDJ(9,3,3)+周MA','pos_boll':'布林带趋势版'}

all_data={}

print(f"\n{'标的':10s}  {'阶段':6s}  {'静态v2':>16s}  {'双RSI':>16s}  {'KDJ':>16s}  {'布林带趋势':>16s}  BNH")
print('─'*95)

for name in ETF_FILES:
    d=load_etf(name)
    d=d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)
    s,r=STATIC_PARAMS[name]
    d=build_v2(d,s,r)
    d=build_dual_rsi(d)
    d=build_kdj(d)
    d=build_boll_trend(d)

    etf={'name':name,'phases':{}}
    for plbl,ps,pe in PHASES:
        phase={}
        for col in STRATS:
            res=backtest(d,col,ps,pe)
            if res: phase[col]={**res,'label':LABELS[col]}
        etf['phases'][plbl]=phase
    all_data[name]=etf

    for plbl,ps,pe in PHASES:
        ph=etf['phases'][plbl]
        bnh=ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return',0)
        vals=[ph.get(c,{}).get('metrics',{}) for c in STRATS]
        best_a=max((v.get('alpha',-999) for v in vals if v),default=0)
        row=f"{name:10s}  {plbl:6s}  "
        for m in vals:
            if m:
                mk='★' if abs(m.get('alpha',0)-best_a)<0.05 else ' '
                row+=f"{mk}{m['total_return']:+6.1f}%(α{m['alpha']:+.1f})  "
            else: row+="         —         "
        print(row+f"BNH:{bnh:+.1f}%")
    print()

out=OUTPUT/'extended_compare3_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data,f,ensure_ascii=False,default=str)
print(f"\n保存: {out}")
