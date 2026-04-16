#!/usr/bin/env python3
"""分阶段对比：静态v2 vs 双均线 vs 多周期共振 vs 海龟CTA"""

import pandas as pd, numpy as np, json
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
PHASES = [
    ("全期",   "2023-04-17", "2026-04-15"),
    ("熊市",   "2023-04-17", "2024-09-19"),
    ("牛市",   "2024-09-20", "2026-04-15"),
]
STRATS = ['pos_v2','pos_dual_ma','pos_multi_tf','pos_turtle']
LABELS = {'pos_v2':'静态v2','pos_dual_ma':'双均线','pos_multi_tf':'多周期共振','pos_turtle':'海龟CTA'}

# ── signal helpers ──────────────────────────────────
def load_etf(name):
    df = pd.read_csv(UPLOADS/ETF_FILES[name], encoding='utf-8-sig')
    df = df.rename(columns={'日期':'date','开盘':'open','收盘':'close','最高':'high','最低':'low'})
    df['date'] = pd.to_datetime(df['date'])
    return df[['date','open','high','low','close']].sort_values('date').reset_index(drop=True)

def classify(o,h,l,c,thr):
    amp=(h-l)/o; return FLAT if amp<thr else (UP if c>=o else DOWN)
def amp_pct(o,h,l): return (h-l)/o*100.0
def seven_rules(dp,dc,ap,ac,prev,st,rt):
    raw=None
    if   dp==UP and dc==UP:   raw=1
    elif dp==DOWN and dc==DOWN: raw=-1
    elif dp==UP and dc==DOWN: raw=-1
    elif dp==DOWN and dc==UP: raw=1
    elif (dp==FLAT or dp==UP) and (dc==UP or dc==FLAT):   return 1
    elif (dp==FLAT or dp==DOWN) and (dc==DOWN or dc==FLAT): return 0
    elif dp==FLAT and dc==FLAT: return prev
    else: return prev
    diff=abs(ac-ap); thr2=st if (dp>0)==(dc>0) else rt
    if diff<thr2: return prev
    return max(raw,0)

def build_all(d, s_thr, r_thr):
    d=d.copy(); n=len(d)
    o=d['open'].values; h=d['high'].values; l=d['low'].values; c=d['close'].values

    # WTS
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

    # DTS → v2
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

    # 双均线 MA5/MA20
    sig=(d['close'].rolling(5).mean()>d['close'].rolling(20).mean()).astype(int)
    d['pos_dual_ma']=sig.shift(1).fillna(0).astype(int)

    # 多周期共振
    d['wk_close']=d.groupby('wk')['close'].transform('last')
    wk_ma=d.groupby('wk')['close'].last().rolling(20).mean()
    wk_bull=(d.groupby('wk')['close'].last()>wk_ma).astype(int).shift(1).fillna(0)
    d['wk_bull']=d['wk'].map(wk_bull).fillna(0).astype(int)
    day_bull=(d['close']>d['close'].rolling(5).mean()).astype(int).shift(1).fillna(0).astype(int)
    d['pos_multi_tf']=((d['wk_bull']==1)&(day_bull==1)).astype(int)

    # 海龟
    don_h=d['close'].rolling(20).max().shift(1)
    don_l=d['close'].rolling(10).min().shift(1)
    pos=0; tpos=[]
    for i,row in d.iterrows():
        if pd.isna(don_h.iloc[i]) or pd.isna(don_l.iloc[i]): tpos.append(0); continue
        if pos==0 and row['close']>don_h.iloc[i]: pos=1
        elif pos==1 and row['close']<don_l.iloc[i]: pos=0
        tpos.append(pos)
    d['pos_turtle']=pd.Series(tpos).shift(1).fillna(0).astype(int).values
    return d

def backtest_seg(d_full, pos_col, start, end, init=1_000_000.0):
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
                shares=cash*(1-COST_BPS/10000)/o; cash=0.0; ep=o*(1+COST_BPS/10000); ed=d['date'].iloc[i]
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

# ── Main ────────────────────────────────────────────
all_data = {}
for name in ETF_FILES:
    d=load_etf(name)
    d=d[(d['date']>='2023-04-17')&(d['date']<='2026-04-15')].reset_index(drop=True)
    s,r=STATIC_PARAMS[name]; d=build_all(d,s,r)
    etf={'name':name,'phases':{}}
    for plbl,ps,pe in PHASES:
        phase={}
        for col in STRATS:
            res=backtest_seg(d,col,ps,pe)
            if res: phase[col]={**res,'label':LABELS[col]}
        etf['phases'][plbl]=phase
    all_data[name]=etf

# Print phase table
for plbl,_,_ in PHASES:
    print(f"\n{'='*80}")
    print(f"  阶段: {plbl}")
    print(f"{'标的':10s}  {'静态v2':>14s}  {'双均线':>14s}  {'多周期共振':>14s}  {'海龟CTA':>14s}  {'BNH':>7s}")
    print('─'*80)
    for name,etf in all_data.items():
        ph=etf['phases'].get(plbl,{})
        if not ph: continue
        bnh=ph['pos_v2']['metrics']['bnh_return'] if 'pos_v2' in ph else 0
        vals=[ph.get(c,{}).get('metrics',{}) for c in STRATS]
        row=f"{name:10s}  "
        for m in vals:
            if m:
                best_marker='*' if m.get('alpha',0)==max(v.get('alpha',-999) for v in vals if v) else ' '
                row+=f"{best_marker}{m['total_return']:+5.1f}%(α{m['alpha']:+.1f})  "
            else: row+="      —         "
        row+=f"BNH:{bnh:+5.1f}%"
        print(row)

out=OUTPUT/'phase_compare_results.json'
with open(out,'w',encoding='utf-8') as f:
    json.dump(all_data,f,ensure_ascii=False,default=str)
print(f"\n保存: {out}")
