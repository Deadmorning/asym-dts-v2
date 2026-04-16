#!/usr/bin/env python3
"""
扩展策略对比：加入 SuperTrend / ADX+MA / MACD / Chandelier Exit
目的：验证静态v2是否真的优于"最相似的"经典技术指标策略
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
PHASES = [("熊市","2023-04-17","2024-09-19"),("牛市","2024-09-20","2026-04-15"),("全期","2023-04-17","2026-04-15")]

# ─────────────────────────────────────────────
def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

# ─────────────────────────────────────────────
# v2 signal (same as before)
# ─────────────────────────────────────────────
def classify(o,h,l,c,thr):
    return FLAT if (h-l)/o<thr else (UP if c>=o else DOWN)
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

def build_v2(d,s_thr,r_thr):
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

# ─────────────────────────────────────────────
# ATR helper
# ─────────────────────────────────────────────
def atr(d, n=14):
    h=d['high']; l=d['low']; c=d['close']
    tr=pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

# ─────────────────────────────────────────────
# SuperTrend (ATR multiplier=3, period=10)
# ─────────────────────────────────────────────
def build_supertrend(d, atr_period=10, mult=3.0):
    d=d.copy()
    a=atr(d, atr_period)
    hl2=(d['high']+d['low'])/2
    upper_band=hl2+mult*a; lower_band=hl2-mult*a
    n=len(d)
    # rolling SuperTrend calculation
    st=np.zeros(n); trend=np.zeros(n,dtype=int); pos=1
    upper=upper_band.values; lower=lower_band.values; c=d['close'].values
    fu=upper[0]; fl=lower[0]
    for i in range(n):
        if i==0: st[i]=upper[i]; trend[i]=1; fu=upper[i]; fl=lower[i]; continue
        # Update bands
        fl = lower[i] if lower[i]>fl or c[i-1]<fl else fl
        fu = upper[i] if upper[i]<fu or c[i-1]>fu else fu
        if trend[i-1]==-1:  # was bearish
            if c[i]>fu: trend[i]=1; st[i]=fl
            else: trend[i]=-1; st[i]=fu
        else:  # was bullish
            if c[i]<fl: trend[i]=-1; st[i]=fu
            else: trend[i]=1; st[i]=fl
    # Signal: trend==1 → long, shift by 1 (signal from prev close)
    d['pos_supertrend']=pd.Series((trend==1).astype(int)).shift(1).fillna(0).astype(int).values
    return d

# ─────────────────────────────────────────────
# ADX + MA20 (ADX>20 confirms trend, MA20 direction)
# ─────────────────────────────────────────────
def build_adx_ma(d, adx_period=14, ma_period=20, adx_thr=20):
    d=d.copy()
    h=d['high'].values; l=d['low'].values; c=d['close'].values; n=len(d)
    # True Range
    tr=np.zeros(n)
    for i in range(1,n):
        tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    # +DM / -DM
    pdm=np.zeros(n); ndm=np.zeros(n)
    for i in range(1,n):
        up=h[i]-h[i-1]; dn=l[i-1]-l[i]
        if up>dn and up>0: pdm[i]=up
        if dn>up and dn>0: ndm[i]=dn
    # Smoothed
    def smooth(arr, p):
        s=np.zeros(n); s[p-1]=arr[:p].sum()
        for i in range(p,n): s[i]=s[i-1]-s[i-1]/p+arr[i]
        return s
    str_=smooth(tr,adx_period); spd=smooth(pdm,adx_period); snd=smooth(ndm,adx_period)
    pdi=100*spd/(str_+1e-9); ndi=100*snd/(str_+1e-9)
    dx=100*np.abs(pdi-ndi)/(pdi+ndi+1e-9)
    adx_=np.zeros(n); adx_[adx_period-1]=dx[:adx_period].mean()
    for i in range(adx_period,n):
        adx_[i]=adx_[i-1]*(adx_period-1)/adx_period+dx[i]/adx_period
    d['adx']=adx_; d['pdi']=pdi; d['ndi']=ndi
    d['ma']=d['close'].rolling(ma_period).mean()
    # Signal: ADX>thr AND +DI>-DI AND close>MA → long
    sig=((d['adx']>adx_thr)&(d['pdi']>d['ndi'])&(d['close']>d['ma'])).astype(int)
    d['pos_adx_ma']=sig.shift(1).fillna(0).astype(int)
    return d

# ─────────────────────────────────────────────
# MACD (12/26/9) — long when MACD line > Signal line
# ─────────────────────────────────────────────
def build_macd(d, fast=12, slow=26, signal=9):
    d=d.copy()
    ema_f=d['close'].ewm(span=fast,adjust=False).mean()
    ema_s=d['close'].ewm(span=slow,adjust=False).mean()
    macd=ema_f-ema_s; sig_line=macd.ewm(span=signal,adjust=False).mean()
    # Long when MACD > Signal (momentum positive)
    pos_sig=(macd>sig_line).astype(int).shift(1).fillna(0).astype(int)
    d['pos_macd']=pos_sig
    return d

# ─────────────────────────────────────────────
# Chandelier Exit (ATR×3 trailing stop)
# ─────────────────────────────────────────────
def build_chandelier(d, atr_period=22, mult=3.0):
    d=d.copy()
    a=atr(d,atr_period)
    c_arr=d['close'].values; n=len(d); a_arr=a.values
    long_stop=np.zeros(n); short_stop=np.zeros(n)
    trend_c=np.ones(n,dtype=int)  # 1=long, -1=short
    for i in range(atr_period, n):
        ls=c_arr[i]-mult*a_arr[i]
        ss=c_arr[i]+mult*a_arr[i]
        long_stop[i]=max(ls, long_stop[i-1]) if c_arr[i-1]>long_stop[i-1] else ls
        short_stop[i]=min(ss, short_stop[i-1]) if c_arr[i-1]<short_stop[i-1] else ss
        if trend_c[i-1]==1:
            trend_c[i]=1 if c_arr[i]>long_stop[i] else -1
        else:
            trend_c[i]=-1 if c_arr[i]<short_stop[i] else 1
    # Long only: trend==1
    d['pos_chandelier']=pd.Series((trend_c==1).astype(int)).shift(1).fillna(0).astype(int).values
    return d

# ─────────────────────────────────────────────
# Backtest engine
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
STRATS = ['pos_v2','pos_supertrend','pos_adx_ma','pos_macd','pos_chandelier']
LABELS = {
    'pos_v2':          '静态v2（本策略）',
    'pos_supertrend':  'SuperTrend ATR3×10',
    'pos_adx_ma':      'ADX20+MA20',
    'pos_macd':        'MACD 12/26/9',
    'pos_chandelier':  'Chandelier ATR3×22',
}

all_data = {}

for name in ETF_FILES:
    print(f"\n[{name}]")
    d=load_etf(name)
    d=d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)
    s,r=STATIC_PARAMS[name]
    d=build_v2(d,s,r)
    d=build_supertrend(d)
    d=build_adx_ma(d)
    d=build_macd(d)
    d=build_chandelier(d)

    etf={'name':name,'phases':{}}
    for plbl,ps,pe in PHASES:
        phase={}
        for col in STRATS:
            res=backtest(d,col,ps,pe)
            if res: phase[col]={**res,'label':LABELS[col]}
        etf['phases'][plbl]=phase
        m=[phase.get(c,{}).get('metrics',{}) for c in STRATS]
        bnh=m[0].get('bnh_return',0) if m[0] else 0
        print(f"  {plbl}: "+' | '.join([f"{LABELS[STRATS[i]][:6]} α{m[i].get('alpha',0):+.1f}%" if m[i] else '—' for i in range(len(STRATS))]) + f" | BNH {bnh:+.1f}%")
    all_data[name]=etf

out=OUTPUT/'extended_compare_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data,f,ensure_ascii=False,default=str)
print(f"\n保存: {out}")
