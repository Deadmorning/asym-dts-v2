#!/usr/bin/env python3
"""
扩展对比 Round 2：补充最相似的亚洲主流策略
  - 一目均衡表 Ichimoku Cloud
  - Parabolic SAR
  - Elder 三重滤网 (Triple Screen)
  - Heikin-Ashi 趋势跟踪
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

def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

# ─── v2 (unchanged) ───────────────────────────────────────
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

# ─── 一目均衡表 Ichimoku ──────────────────────────────────
def build_ichimoku(d):
    d=d.copy()
    h=d['high']; l=d['low']; c=d['close']
    # 转换线 (Tenkan) = (9日最高+9日最低)/2
    tenkan  = (h.rolling(9).max()  + l.rolling(9).min())  / 2
    # 基准线 (Kijun)  = (26日最高+26日最低)/2
    kijun   = (h.rolling(26).max() + l.rolling(26).min()) / 2
    # 先行带A = (转换+基准)/2，向前位移26期
    span_a  = ((tenkan + kijun) / 2).shift(26)
    # 先行带B = (52日最高+52日最低)/2，向前位移26期
    span_b  = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    # 云层上下轨（当日对应的是26期前发布的云）
    # 我们用 shift(-26) 来取"当日"云值（避免未来数据：用当时已知的云区间）
    cloud_top    = pd.concat([span_a, span_b], axis=1).max(axis=1)
    cloud_bottom = pd.concat([span_a, span_b], axis=1).min(axis=1)

    # 信号：close > cloud_top（多头区域）AND 转换线 > 基准线（动量确认）
    # 全部用前一日信号避免 look-ahead
    bull = ((c > cloud_top) & (tenkan > kijun)).astype(int)
    d['pos_ichimoku'] = bull.shift(1).fillna(0).astype(int)
    return d

# ─── Parabolic SAR ───────────────────────────────────────
def build_psar(d, af_start=0.02, af_step=0.02, af_max=0.20):
    d=d.copy()
    h=d['high'].values; l=d['low'].values; n=len(d)
    sar=np.zeros(n); trend=np.ones(n,dtype=int); ep=np.zeros(n); af=np.zeros(n)

    sar[0]=l[0]; ep[0]=h[0]; af[0]=af_start; trend[0]=1
    for i in range(1,n):
        if trend[i-1]==1:
            sar[i]=sar[i-1]+af[i-1]*(ep[i-1]-sar[i-1])
            sar[i]=min(sar[i],l[i-2] if i>=2 else l[i-1],l[i-1])
            if l[i]<sar[i]:
                trend[i]=-1; sar[i]=ep[i-1]; ep[i]=l[i]; af[i]=af_start
            else:
                trend[i]=1
                ep[i]=max(ep[i-1],h[i])
                af[i]=min(af[i-1]+af_step,af_max) if h[i]>ep[i-1] else af[i-1]
        else:
            sar[i]=sar[i-1]+af[i-1]*(ep[i-1]-sar[i-1])
            sar[i]=max(sar[i],h[i-2] if i>=2 else h[i-1],h[i-1])
            if h[i]>sar[i]:
                trend[i]=1; sar[i]=ep[i-1]; ep[i]=h[i]; af[i]=af_start
            else:
                trend[i]=-1
                ep[i]=min(ep[i-1],l[i])
                af[i]=min(af[i-1]+af_step,af_max) if l[i]<ep[i-1] else af[i-1]

    # Long only when trend=1, signal from previous day
    d['pos_psar'] = pd.Series((trend==1).astype(int)).shift(1).fillna(0).astype(int).values
    return d

# ─── Elder 三重滤网 (Triple Screen) ──────────────────────
# 高周期：周线 MACD histogram 方向（趋势过滤）
# 低周期：日线 Stochastic %K 超卖反弹（进场触发）
def build_triple_screen(d):
    d=d.copy()
    c=d['close']; h=d['high']; l=d['low']

    # 周线 MACD histogram
    d['wk']=d['date'].dt.to_period('W')
    wk_close=d.groupby('wk')['close'].last()
    ema_f=wk_close.ewm(span=12,adjust=False).mean()
    ema_s=wk_close.ewm(span=26,adjust=False).mean()
    macd_w=ema_f-ema_s; sig_w=macd_w.ewm(span=9,adjust=False).mean()
    hist_w=macd_w-sig_w
    # 周线趋势：histogram上升（连续2周）= 多头
    hist_rising=(hist_w>hist_w.shift(1)).astype(int).shift(1).fillna(0)  # 前一周判断
    d['wk_trend']=d['wk'].map(hist_rising).fillna(0).astype(int)

    # 日线 Stochastic %K (5,3)
    low5=l.rolling(5).min(); high5=h.rolling(5).max()
    k=(c-low5)/(high5-low5+1e-9)*100
    k_smooth=k.rolling(3).mean()
    # 进场：日线%K从超卖区（<30）向上穿过 → 买入，高周期多头时有效
    entry=((k_smooth>30)&(k_smooth.shift(1)<30)).astype(int)
    # 持仓：高周期多头 + 日线K未超买（<70）
    hold=((d['wk_trend']==1)&(k_smooth<70)).astype(int)
    # 组合：进场触发或持仓中
    pos=0; signals=[]; prev_pos=0
    entry_arr=entry.fillna(0).values; hold_arr=hold.fillna(0).values
    wt=d['wk_trend'].values
    for i in range(len(d)):
        if wt[i]==0: pos=0
        elif entry_arr[i]==1 and prev_pos==0: pos=1
        elif hold_arr[i]==0 and pos==1: pos=0
        signals.append(pos); prev_pos=pos
    d['pos_triple']=pd.Series(signals).shift(1).fillna(0).astype(int).values
    return d

# ─── Heikin-Ashi 趋势 ────────────────────────────────────
def build_heikin_ashi(d, ma_filter=20):
    d=d.copy()
    o=d['open'].values; h=d['high'].values; l=d['low'].values; c=d['close'].values
    n=len(d)
    # HA candles
    ha_c=np.zeros(n); ha_o=np.zeros(n); ha_h=np.zeros(n); ha_l=np.zeros(n)
    ha_c[0]=(o[0]+h[0]+l[0]+c[0])/4; ha_o[0]=(o[0]+c[0])/2
    for i in range(1,n):
        ha_c[i]=(o[i]+h[i]+l[i]+c[i])/4
        ha_o[i]=(ha_o[i-1]+ha_c[i-1])/2
        ha_h[i]=max(h[i],ha_o[i],ha_c[i])
        ha_l[i]=min(l[i],ha_o[i],ha_c[i])
    # HA 蜡烛为阳线 = ha_c > ha_o
    ha_bull=(ha_c>ha_o).astype(int)
    # 连续N根阳线确认趋势（N=2）
    ha_series=pd.Series(ha_bull)
    ha_consec=(ha_series.astype(bool) & ha_series.shift(1).fillna(0).astype(bool)).astype(int)  # 连续2根阳线
    # 可选：加MA20过滤（收盘>MA20才入场）
    ma=d['close'].rolling(ma_filter).mean()
    bull_filter=(d['close']>ma).astype(int)
    sig=(ha_consec & bull_filter).astype(int)
    d['pos_ha']=sig.shift(1).fillna(0).astype(int)
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
STRATS = ['pos_v2','pos_ichimoku','pos_psar','pos_triple','pos_ha']
LABELS = {
    'pos_v2':       '静态v2（本策略）',
    'pos_ichimoku': '一目均衡表 Ichimoku',
    'pos_psar':     'Parabolic SAR',
    'pos_triple':   'Elder三重滤网',
    'pos_ha':       'Heikin-Ashi+MA20',
}

all_data = {}
print(f"{'标的':10s}  {'静态v2':>14s}  {'Ichimoku':>14s}  {'PSAR':>14s}  {'Triple':>14s}  {'HA':>14s}")
print('─'*90)

for name in ETF_FILES:
    d=load_etf(name)
    d=d[(d['date']>=FULL_START)&(d['date']<=FULL_END)].reset_index(drop=True)
    s,r=STATIC_PARAMS[name]
    d=build_v2(d,s,r)
    d=build_ichimoku(d)
    d=build_psar(d)
    d=build_triple_screen(d)
    d=build_heikin_ashi(d)

    etf={'name':name,'phases':{}}
    for plbl,ps,pe in PHASES:
        phase={}
        for col in STRATS:
            res=backtest(d,col,ps,pe)
            if res: phase[col]={**res,'label':LABELS[col]}
        etf['phases'][plbl]=phase
    all_data[name]=etf

    # Print full period
    ph=etf['phases']['全期']; bnh=ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return',0)
    vals=[ph.get(c,{}).get('metrics',{}) for c in STRATS]
    best_a=max((v.get('alpha',-999) for v in vals if v),default=0)
    row=f"{name:10s}  "
    for m in vals:
        if m:
            mk='*' if abs(m.get('alpha',0)-best_a)<0.05 else ' '
            row+=f"{mk}{m['total_return']:+5.1f}%(α{m['alpha']:+.1f})  "
        else: row+="      —           "
    print(row+f"BNH:{bnh:+.1f}%")

# Print bear / bull
for plbl,_,_ in PHASES[:2]:
    print(f"\n{'='*85}  阶段:{plbl}")
    for name,etf in all_data.items():
        ph=etf['phases'].get(plbl,{}); bnh=ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return',0)
        vals=[ph.get(c,{}).get('metrics',{}) for c in STRATS]
        best_a=max((v.get('alpha',-999) for v in vals if v),default=0)
        row=f"  {name:10s}  "
        for m in vals:
            if m:
                mk='*' if abs(m.get('alpha',0)-best_a)<0.05 else ' '
                row+=f"{mk}α{m['alpha']:+.1f}%  "
        print(row+f"BNH:{bnh:+.1f}%")

out=OUTPUT/'extended_compare2_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data,f,ensure_ascii=False,default=str)
print(f"\n保存: {out}")
