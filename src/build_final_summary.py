#!/usr/bin/env python3
"""
15种策略终极总结：合并三轮数据，生成完整分析报告
"""
import json
from pathlib import Path

OUTPUT = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")

with open(OUTPUT/'extended_compare_results.json','r',encoding='utf-8') as f: d1=json.load(f)
with open(OUTPUT/'extended_compare2_results.json','r',encoding='utf-8') as f: d2=json.load(f)
with open(OUTPUT/'extended_compare3_results.json','r',encoding='utf-8') as f: d3=json.load(f)

ETF_NAMES = list(d1.keys())
PHASES = ["熊市","牛市","全期"]

# All 15 strategies with metadata
STRATS = {
    'pos_v2':         {'label':'静态v2（本策略）',     'color':'#1a73e8','src':'r2','short':'v2'},
    'pos_dual_ma':    {'label':'双均线 MA5/20',        'color':'#e53935','src':'r1','short':'双均线'},
    'pos_multi_tf':   {'label':'多周期共振',            'color':'#f57c00','src':'r1','short':'多周期'},
    'pos_turtle':     {'label':'海龟CTA N20/10',       'color':'#7b1fa2','src':'r1','short':'海龟'},
    'pos_supertrend': {'label':'SuperTrend ATR×3',    'color':'#00acc1','src':'r1','short':'SuperTrend'},
    'pos_adx_ma':     {'label':'ADX20+MA20',           'color':'#43a047','src':'r1','short':'ADX+MA'},
    'pos_macd':       {'label':'MACD 12/26/9',         'color':'#fb8c00','src':'r1','short':'MACD'},
    'pos_chandelier': {'label':'Chandelier ATR×3',     'color':'#8e24aa','src':'r1','short':'Chandelier'},
    'pos_ichimoku':   {'label':'Ichimoku 一目均衡',     'color':'#0097a7','src':'r2','short':'Ichimoku'},
    'pos_psar':       {'label':'Parabolic SAR',         'color':'#558b2f','src':'r2','short':'PSAR'},
    'pos_triple':     {'label':'Elder 三重滤网',         'color':'#e65100','src':'r2','short':'三重滤网'},
    'pos_ha':         {'label':'Heikin-Ashi+MA20',     'color':'#6a1b9a','src':'r2','short':'Heikin-Ashi'},
    'pos_dual_rsi':   {'label':'双RSI(14,50)',          'color':'#c62828','src':'r3','short':'双RSI'},
    'pos_kdj':        {'label':'KDJ(9,3,3)+周MA',      'color':'#827717','src':'r3','short':'KDJ'},
    'pos_boll':       {'label':'布林带趋势版',           'color':'#37474f','src':'r3','short':'布林带'},
}
ALL_STRATS = list(STRATS.keys())

DS = {'r1':d1,'r2':d2,'r3':d3}

def get_m(etf, strat, phase):
    src = STRATS[strat]['src']
    return DS[src].get(etf,{}).get('phases',{}).get(phase,{}).get(strat,{}).get('metrics',{})

def get_cum(etf, strat, phase):
    src = STRATS[strat]['src']
    return DS[src].get(etf,{}).get('phases',{}).get(phase,{}).get(strat,{}).get('cum_ret',[])

def get_bnh_ret(etf, phase):
    return DS['r1'].get(etf,{}).get('phases',{}).get(phase,{}).get('pos_v2',{}).get('bnh_ret',[])

def get_dates(etf, phase):
    return DS['r1'].get(etf,{}).get('phases',{}).get(phase,{}).get('pos_v2',{}).get('dates',[])

# ─── Build full alpha matrix ─────────────────────────────
def build_alpha_matrix():
    """Returns {etf: {phase: {strat: alpha}}}"""
    mat = {}
    for name in ETF_NAMES:
        mat[name] = {}
        for phase in PHASES:
            mat[name][phase] = {}
            for s in ALL_STRATS:
                m = get_m(name, s, phase)
                mat[name][phase][s] = m.get('alpha', None) if m else None
    return mat

mat = build_alpha_matrix()

# ─── Strategy profile analysis ───────────────────────────
def analyze_strategy(strat):
    """Summarize a strategy's performance across all ETFs and phases."""
    bear_alphas=[]; bull_alphas=[]; full_alphas=[]
    for name in ETF_NAMES:
        b=mat[name]['熊市'].get(strat)
        u=mat[name]['牛市'].get(strat)
        f=mat[name]['全期'].get(strat)
        if b is not None: bear_alphas.append(b)
        if u is not None: bull_alphas.append(u)
        if f is not None: full_alphas.append(f)
    return {
        'bear_avg': round(sum(bear_alphas)/len(bear_alphas),1) if bear_alphas else None,
        'bull_avg': round(sum(bull_alphas)/len(bull_alphas),1) if bull_alphas else None,
        'full_avg': round(sum(full_alphas)/len(full_alphas),1) if full_alphas else None,
        'bear_wins': sum(1 for a in bear_alphas if a>0),
        'bull_wins': sum(1 for a in bull_alphas if a>0),
        'full_wins': sum(1 for a in full_alphas if a>0),
    }

profiles = {s: analyze_strategy(s) for s in ALL_STRATS}

# ─── Alpha heatmap tables (one per phase) ────────────────
def color_cell(alpha, best_alpha):
    if alpha is None: return '<td style="color:#444">—</td>'
    is_best = best_alpha is not None and abs(alpha - best_alpha) < 0.1
    intensity = min(abs(alpha)/30, 1.0)
    if alpha >= 0:
        bg = f'rgba(76,175,80,{intensity*0.35:.2f})' if is_best else f'rgba(76,175,80,{intensity*0.18:.2f})'
        col = '#a5d6a7'
    else:
        bg = f'rgba(239,83,80,{intensity*0.35:.2f})'
        col = '#ef9a9a'
    star = '★' if is_best else ''
    border = 'border:1px solid #ffd54f;' if is_best else ''
    return f'<td style="background:{bg};{border}"><span style="color:{col};font-size:.75rem">{star}{alpha:+.1f}%</span></td>'

def build_phase_table(phase):
    hdr = '<tr><th>标的/策略</th>' + ''.join([
        f'<th style="color:{STRATS[s]["color"]};font-size:.72rem;writing-mode:vertical-rl;padding:4px 2px;min-width:28px">{STRATS[s]["short"]}</th>'
        for s in ALL_STRATS
    ]) + '<th>BNH</th></tr>'
    rows = ''
    for name in ETF_NAMES:
        alphas = {s: mat[name][phase].get(s) for s in ALL_STRATS}
        valid = [a for a in alphas.values() if a is not None]
        best_a = max(valid) if valid else None
        bnh_r = get_m(name,'pos_v2',phase).get('bnh_return',0)
        cells = f'<td class="en">{name}</td>'
        for s in ALL_STRATS:
            cells += color_cell(alphas[s], best_a)
        cells += f'<td class="bc">{bnh_r:+.1f}%</td>'
        rows += f'<tr>{rows}{cells}</tr>\n'
    # Add avg row
    avg_cells = '<td class="avg-row">平均α</td>'
    for s in ALL_STRATS:
        vals = [mat[n][phase].get(s) for n in ETF_NAMES if mat[n][phase].get(s) is not None]
        avg = sum(vals)/len(vals) if vals else None
        if avg is None: avg_cells += '<td>—</td>'
        else:
            col='#a5d6a7' if avg>=0 else '#ef9a9a'
            avg_cells += f'<td><span style="color:{col};font-weight:700;font-size:.75rem">{avg:+.1f}%</span></td>'
    avg_cells += '<td>—</td>'
    rows += f'<tr class="avg-tr">{avg_cells}</tr>'
    return f'<table class="htbl">{hdr}{rows}</table>'

# ─── Strategy score cards JS ─────────────────────────────
scorecard_data = []
for s in ALL_STRATS:
    p = profiles[s]
    scorecard_data.append({
        'id': s, 'label': STRATS[s]['label'], 'color': STRATS[s]['color'],
        'bear_avg': p['bear_avg'], 'bull_avg': p['bull_avg'], 'full_avg': p['full_avg'],
        'bear_wins': p['bear_wins'], 'bull_wins': p['bull_wins'], 'full_wins': p['full_wins'],
    })

# ─── Best strategy matrix ─────────────────────────────────
def best_strat_matrix():
    # For each ETF × phase, find best and 2nd best
    rows = ''
    phase_colors = {'熊市':'#ef9a9a','牛市':'#a5d6a7','全期':'#90caf9'}
    for name in ETF_NAMES:
        row = f'<td class="en">{name}</td>'
        for phase in PHASES:
            alphas = {s: mat[name][phase].get(s) for s in ALL_STRATS if mat[name][phase].get(s) is not None}
            if not alphas:
                row += '<td>—</td>'; continue
            sorted_s = sorted(alphas.items(), key=lambda x: x[1], reverse=True)
            best = sorted_s[0]; second = sorted_s[1] if len(sorted_s)>1 else None
            c1 = STRATS[best[0]]['color']
            s1 = STRATS[best[0]]['short']
            a1 = best[1]
            col_a1 = '#a5d6a7' if a1>=0 else '#ef9a9a'
            cell = f'<span style="color:{c1};font-weight:700">{s1}</span><br><span style="color:{col_a1};font-size:.72rem">α{a1:+.1f}%</span>'
            if second:
                c2=STRATS[second[0]]['color']; s2=STRATS[second[0]]['short']; a2=second[1]
                col_a2='#a5d6a7' if a2>=0 else '#ef9a9a'
                cell+=f'<br><span style="color:{c2};font-size:.68rem">次:{s2} α{a2:+.1f}%</span>'
            row += f'<td style="text-align:left;padding:6px 8px">{cell}</td>'
        rows += f'<tr>{row}</tr>\n'
    hdr = '<tr><th>标的</th>' + ''.join([f'<th style="color:{phase_colors[p]}">{p}</th>' for p in PHASES]) + '</tr>'
    return f'<table class="htbl">{hdr}{rows}</table>'

# ─── Radar chart data ─────────────────────────────────────
radar_strats = ['pos_v2','pos_dual_rsi','pos_adx_ma','pos_triple','pos_ichimoku','pos_supertrend']
radar_js = ''
for s in radar_strats:
    p = profiles[s]
    b = min(max((p['bear_avg'] or -50)+50, 0)/100*100, 100)
    u = min(max((p['bull_avg'] or -100)+100, 0)/200*100, 100)
    f = min(max((p['full_avg'] or -50)+50, 0)/100*100, 100)
    bw = (p['bear_wins'] or 0)/6*100
    uw = (p['bull_wins'] or 0)/6*100
    # score: bear protection, bull capture, full period, stability(full wins)
    radar_js += f"charts.push({{name:'{STRATS[s]['label']}',color:'{STRATS[s]['color']}',data:[{b:.0f},{u:.0f},{f:.0f},{bw:.0f},{uw:.0f}]}});\n"

# ─── Equity curve charts ─────────────────────────────────
eq_charts = ''
for name in ETF_NAMES:
    sid = 'eq_'+''.join(c for c in name if c.isalnum())
    dates = get_dates(name,'全期')
    bnh = get_bnh_ret(name,'全期')
    # Pick 5 best strategies for readability
    sorted_s = sorted(ALL_STRATS, key=lambda s: (mat[name]['全期'].get(s) or -999), reverse=True)[:5]
    series = []
    for s in sorted_s:
        cum = get_cum(name,s,'全期')
        if cum:
            lw = 2.5 if s=='pos_v2' else 1.8
            series.append(f'{{name:"{STRATS[s]["short"]}",data:{json.dumps(cum)},color:"{STRATS[s]["color"]}",lineWidth:{lw}}}')
    if bnh:
        series.append(f'{{name:"BNH",data:{json.dumps(bnh)},color:"#555",lineWidth:1.5,dashStyle:"Dot"}}')
    eq_charts += f"""
    Highcharts.chart('{sid}',{{
      chart:{{backgroundColor:'#1a1d27',height:240,margin:[30,10,40,50]}},
      title:{{text:'{name}',style:{{color:'#ccc',fontSize:'12px'}},align:'left',x:8,y:8}},
      xAxis:{{categories:{json.dumps(dates)},tickInterval:Math.floor({len(dates)}/6)||1,
        labels:{{style:{{color:'#666',fontSize:'9px'}},rotation:-30}},gridLineColor:'#1e2030',lineColor:'#2a2d3a'}},
      yAxis:{{title:{{text:null}},labels:{{style:{{color:'#777',fontSize:'9px'}},format:'{{value}}%'}},
        gridLineColor:'#1e2030',plotLines:[{{value:0,color:'#444',width:1}}]}},
      legend:{{itemStyle:{{color:'#999',fontSize:'9px'}},maxHeight:40}},
      tooltip:{{shared:true,valueDecimals:1,valueSuffix:'%',backgroundColor:'rgba(15,17,23,.95)',borderColor:'#333',style:{{color:'#eee'}}}},
      series:[{','.join(series)}],credits:{{enabled:false}},
      plotOptions:{{series:{{animation:false,marker:{{enabled:false}}}}}}
    }});"""

# ─── Recommendation cards ─────────────────────────────────
RECO = [
    {
        'title':'稳定趋势型 ETF',
        'etfs':'深证100、中证500、上证50',
        'desc':'熊市跌势渐进、牛市趋势平稳，振幅信号有效',
        'bear':'静态v2',
        'bull':'静态v2',
        'full':'静态v2',
        'why_bear':'振幅过滤精准识别熊市压力，α+27~+17%',
        'why_bull':'牛市损耗小（深证100 α-8.9%），远优于其他策略',
        'why_full':'全期5/6 ETF第一，深证100 α+35.9%',
    },
    {
        'title':'爆发型高弹性 ETF',
        'etfs':'科创50、创业板',
        'desc':'牛市暴涨集中、单日涨幅大，细粒度信号容易被大波动误触发',
        'bear':'静态v2',
        'bull':'双RSI',
        'full':'双RSI',
        'why_bear':'熊市v2和双RSI表现接近（科创50 α≈+44%）',
        'why_bull':'双RSI平滑钝感，不被单日大阴线触发退场，科创50 α-41% vs v2 α-84%',
        'why_full':'双RSI科创50全期 α+52%（v2仅+11.8%）',
    },
    {
        'title':'熊市极端保护需求',
        'etfs':'全品类',
        'desc':'最大化熊市回撤保护，不计牛市损耗',
        'bear':'Elder三重滤网',
        'bull':'慎用（牛市损耗极大）',
        'full':'不推荐',
        'why_bear':'科创50熊市 α+47%，上证50 α+19.5%，创业板 α+34.9%',
        'why_bull':'牛市α普遍-80%~-131%，严重漏单',
        'why_full':'全期净收益往往不如v2和双RSI',
    },
    {
        'title':'创业板/高波动的折中',
        'etfs':'创业板',
        'desc':'v2全期α=-38%，需要替代方案',
        'bear':'Elder三重滤网 / v2',
        'bull':'双RSI',
        'full':'Ichimoku',
        'why_bear':'三重滤网熊市α+34.9%最优',
        'why_bull':'双RSI牛市损耗-100%，比v2的-105%略好',
        'why_full':'Ichimoku全期α-11.8%，是创业板所有策略中损耗最小的',
    },
]

reco_cards = ''
for r in RECO:
    reco_cards += f"""
    <div class="reco-card">
      <div class="reco-title">{r['title']}</div>
      <div class="reco-etfs">{r['etfs']}</div>
      <div class="reco-desc">{r['desc']}</div>
      <table class="reco-tbl">
        <tr><th>阶段</th><th>推荐策略</th><th>理由</th></tr>
        <tr><td class="bear-lbl">熊市</td><td><strong>{r['bear']}</strong></td><td class="why">{r['why_bear']}</td></tr>
        <tr><td class="bull-lbl">牛市</td><td><strong>{r['bull']}</strong></td><td class="why">{r['why_bull']}</td></tr>
        <tr><td class="full-lbl">全期</td><td><strong>{r['full']}</strong></td><td class="why">{r['why_full']}</td></tr>
      </table>
    </div>"""

# ─── Strategy profiles table ──────────────────────────────
strat_profile_rows = ''
STRAT_DETAIL = {
    'pos_v2':         ('振幅过滤 K线7规则 双周期','全能型，稳定趋势ETF首选','高波动ETF牛市易漏单'),
    'pos_dual_ma':    ('MA5/20金叉死叉','简单易懂','均线滞后，A股震荡市频繁假突破'),
    'pos_multi_tf':   ('周MA20+日MA5双均线','双周期过滤','A股周线MA收敛慢，信号延迟严重'),
    'pos_turtle':     ('20日突破入场，10日低点出场','经典趋势跟踪','突破后常回撤，A股假突破多'),
    'pos_supertrend': ('ATR波动带方向跟踪','自适应波动率','ATR乘数固定，A股板块切换快易失效'),
    'pos_adx_ma':     ('ADX>20趋势强度过滤+MA方向','科学趋势强度量化','ADX反应慢，错过趋势初期'),
    'pos_macd':       ('12/26/9 MACD金叉死叉','全球通用，信号标准','信号频繁，A股小振幅噪声大'),
    'pos_chandelier': ('ATR动态止损追踪','动态止损优雅','参数敏感，A股跳空常触发假止损'),
    'pos_ichimoku':   ('云层+转换/基准线多周期','视觉直观多信号确认','参数固定无法适应A股波动特性'),
    'pos_psar':       ('抛物线动态止损追踪','追涨止跌逻辑清晰','A股高波动频繁反转导致参数漂移'),
    'pos_triple':     ('周MACD趋势+日K线触发','熊市保护极强','牛市敏感度低，严重漏单'),
    'pos_ha':         ('HA蜡烛噪声过滤+MA20','去噪效果好','反应过慢，牛市滞后进出'),
    'pos_dual_rsi':   ('周RSI>50方向+日RSI>50持仓','极简两参数，不易过拟合','平滑过度，震荡市假信号多'),
    'pos_kdj':        ('9日KDJ金叉死叉+周MA过滤','A股最熟悉指标','K线过于敏感，A股日内震荡频繁金叉死叉'),
    'pos_boll':       ('突破BB上轨入场，跌破中轨出场','趋势启动信号清晰','突破后常快速回落，信号质量不稳定'),
}
for s in ALL_STRATS:
    p = profiles[s]
    detail = STRAT_DETAIL.get(s,('—','—','—'))
    col = STRATS[s]['color']
    bear_w = f"{p['bear_wins']}/6"
    bull_w = f"{p['bull_wins']}/6"
    full_w = f"{p['full_wins']}/6"
    ba = f"{p['bear_avg']:+.1f}%" if p['bear_avg'] is not None else '—'
    ua = f"{p['bull_avg']:+.1f}%" if p['bull_avg'] is not None else '—'
    fa = f"{p['full_avg']:+.1f}%" if p['full_avg'] is not None else '—'
    ba_col = '#a5d6a7' if (p['bear_avg'] or 0)>=0 else '#ef9a9a'
    ua_col = '#a5d6a7' if (p['bull_avg'] or 0)>=0 else '#ef9a9a'
    fa_col = '#a5d6a7' if (p['full_avg'] or 0)>=0 else '#ef9a9a'
    strat_profile_rows += f"""<tr>
      <td><span style="color:{col};font-weight:700">{STRATS[s]['short']}</span><br><span style="color:#555;font-size:.68rem">{STRATS[s]['label']}</span></td>
      <td style="font-size:.72rem;color:#aaa">{detail[0]}</td>
      <td style="color:{ba_col}">{ba}<br><span style="color:#666;font-size:.7rem">{bear_w} ETF正α</span></td>
      <td style="color:{ua_col}">{ua}<br><span style="color:#666;font-size:.7rem">{bull_w} ETF正α</span></td>
      <td style="color:{fa_col}">{fa}<br><span style="color:#666;font-size:.7rem">{full_w} ETF正α</span></td>
      <td style="font-size:.72rem;color:#66bb6a">{detail[1]}</td>
      <td style="font-size:.72rem;color:#ef9a9a">{detail[2]}</td>
    </tr>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>15种策略终极总结</title>
<script src="https://code.highcharts.com/highcharts.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f1117;color:#e0e0e0;padding:20px;font-size:14px}}
h1{{font-size:1.4rem;font-weight:800;color:#fff;margin-bottom:4px}}
.sub{{color:#666;font-size:.8rem;margin-bottom:22px}}
h2{{font-size:.95rem;font-weight:700;margin-bottom:12px;padding:5px 10px;border-radius:6px;display:inline-block}}
.sec{{background:#1a1d27;border-radius:12px;padding:16px 18px;margin-bottom:18px}}

/* Heatmap table */
.htbl{{width:100%;border-collapse:collapse;font-size:.75rem}}
.htbl th{{background:#12151f;color:#666;padding:5px 4px;text-align:center;border-bottom:1px solid #222;white-space:nowrap}}
.htbl td{{padding:4px 5px;text-align:center;border-bottom:1px solid #1a1e2d}}
.en{{text-align:left;font-weight:600;color:#ddd;white-space:nowrap;padding:5px 8px!important}}
.bc{{color:#666;font-size:.72rem}}
.avg-tr td{{background:#12151f!important;border-top:1px solid #333}}
.avg-row{{color:#888;font-weight:700;text-align:left;padding-left:8px}}
tr:hover td{{background:rgba(255,255,255,.02)}}

/* Tabs */
.tabs{{display:flex;gap:6px;margin-bottom:12px}}
.tab{{padding:6px 14px;border-radius:15px;border:1px solid #2a2d3a;background:transparent;color:#777;cursor:pointer;font-size:.78rem;transition:all .15s}}
.tab.active{{background:#1a73e8;border-color:#1a73e8;color:#fff}}
.panel{{display:none}}.panel.active{{display:block}}

/* Best strategy matrix */
.best-tbl{{width:100%;border-collapse:collapse;font-size:.78rem}}
.best-tbl th{{background:#12151f;color:#888;padding:8px 10px;text-align:center;border-bottom:1px solid #222}}
.best-tbl td{{padding:6px 8px;border-bottom:1px solid #1a1e2d;vertical-align:top}}
.bear-lbl{{color:#ef9a9a;font-weight:700}}.bull-lbl{{color:#a5d6a7;font-weight:700}}.full-lbl{{color:#90caf9;font-weight:700}}

/* Recommendation cards */
.reco-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.reco-card{{background:#12151f;border-radius:10px;padding:14px 16px;border:1px solid #1e2230}}
.reco-title{{font-weight:700;color:#90caf9;font-size:.9rem;margin-bottom:3px}}
.reco-etfs{{font-size:.75rem;color:#ffd54f;margin-bottom:6px}}
.reco-desc{{font-size:.74rem;color:#777;margin-bottom:10px;line-height:1.5}}
.reco-tbl{{width:100%;border-collapse:collapse;font-size:.75rem}}
.reco-tbl th{{background:#1a1d27;color:#666;padding:4px 6px;text-align:left;border-bottom:1px solid #1e2030}}
.reco-tbl td{{padding:5px 6px;border-bottom:1px solid #1a1e2d;vertical-align:top}}
.reco-tbl strong{{color:#fff}}.why{{color:#888;font-size:.7rem;line-height:1.4}}

/* Profile table */
.ptbl{{width:100%;border-collapse:collapse;font-size:.76rem}}
.ptbl th{{background:#12151f;color:#666;padding:6px 8px;text-align:left;border-bottom:1px solid #222;white-space:nowrap}}
.ptbl td{{padding:6px 8px;border-bottom:1px solid #1a1e2d;vertical-align:top}}
.ptbl tr:hover td{{background:rgba(255,255,255,.02)}}

/* Equity grid */
.eq-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
.eq-cell{{background:#12151f;border-radius:8px;padding:4px}}
.eq-tab-btns{{display:flex;gap:5px;margin-bottom:8px;flex-wrap:wrap}}
.etab{{padding:4px 10px;border-radius:12px;border:1px solid #2a2d3a;background:transparent;color:#777;cursor:pointer;font-size:.74rem}}
.etab.active{{background:#1a73e8;border-color:#1a73e8;color:#fff}}
</style>
</head>
<body>
<h1>15种策略终极总结报告</h1>
<p class="sub">三轮测试 · 15种策略 · 6只ETF · 熊市/牛市/全期 · 2023.04–2026.04 · 手续费15bps</p>

<!-- 1. 推荐矩阵 -->
<div class="sec">
<h2 style="background:rgba(144,202,249,.1);color:#90caf9">推荐使用矩阵</h2>
<div class="reco-grid">{reco_cards}</div>
</div>

<!-- 2. 最优策略快查表 -->
<div class="sec">
<h2 style="background:rgba(255,213,79,.08);color:#ffd54f">各ETF各阶段最优策略（含次优）</h2>
{best_strat_matrix()}
</div>

<!-- 3. 15种策略档案 -->
<div class="sec" style="overflow-x:auto">
<h2 style="background:rgba(26,115,232,.1);color:#90caf9">15种策略档案</h2>
<table class="ptbl">
<tr><th>策略</th><th>核心机制</th><th>熊市平均α</th><th>牛市平均α</th><th>全期平均α</th><th>优势</th><th>局限</th></tr>
{strat_profile_rows}
</table>
</div>

<!-- 4. Alpha热力表（分阶段）-->
<div class="sec" style="overflow-x:auto">
<h2 style="background:rgba(255,255,255,.04);color:#ccc">Alpha 热力矩阵（★=各ETF该阶段最高）</h2>
<div class="tabs" id="heatTabs">
  <button class="tab active" onclick="switchTab('heat','bear',this)">熊市</button>
  <button class="tab" onclick="switchTab('heat','bull',this)">牛市</button>
  <button class="tab" onclick="switchTab('heat','full',this)">全期</button>
</div>
<div id="heat_bear" class="panel active">{build_phase_table("熊市")}</div>
<div id="heat_bull" class="panel">{build_phase_table("牛市")}</div>
<div id="heat_full" class="panel">{build_phase_table("全期")}</div>
</div>

<!-- 5. 收益曲线（精选各ETF前5策略）-->
<div class="sec">
<h2 style="background:rgba(255,255,255,.04);color:#ccc">各ETF全期收益曲线（前5策略+BNH）</h2>
<div class="eq-grid" id="eqGrid">
  {''.join([f'<div class="eq-cell"><div id="eq_{"".join(c for c in n if c.isalnum())}" style="height:240px"></div></div>' for n in ETF_NAMES])}
</div>
</div>

<script>
function switchTab(group, id, btn) {{
  const prefix = group+'_';
  document.querySelectorAll(`[id^="${{prefix}}"]`).forEach(p=>p.classList.remove('active'));
  document.getElementById(prefix+id).classList.add('active');
  btn.closest('.sec').querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
}}
window.addEventListener('load', () => {{
  {eq_charts}
}});
</script>
</body>
</html>"""

out = OUTPUT / 'final_15strategy_summary.html'
with open(out,'w',encoding='utf-8') as f: f.write(html)
print(f"saved: {out}  ({out.stat().st_size//1024} KB)")
