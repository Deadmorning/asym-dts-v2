#!/usr/bin/env python3
import json
from pathlib import Path

OUTPUT = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")
with open(OUTPUT/'extended_compare_results.json','r',encoding='utf-8') as f:
    data = json.load(f)

ETF_NAMES = list(data.keys())
STRATS = ['pos_v2','pos_supertrend','pos_adx_ma','pos_macd','pos_chandelier']
LABELS = {
    'pos_v2':         '静态v2',
    'pos_supertrend': 'SuperTrend',
    'pos_adx_ma':     'ADX+MA',
    'pos_macd':       'MACD',
    'pos_chandelier': 'Chandelier',
}
COLORS = {
    'pos_v2':         '#1a73e8',
    'pos_supertrend': '#00acc1',
    'pos_adx_ma':     '#43a047',
    'pos_macd':       '#fb8c00',
    'pos_chandelier': '#8e24aa',
    'bnh':            '#9e9e9e',
}
PHASES = ['熊市','牛市','全期']
PHASE_COLORS = {'熊市':'#ef9a9a','牛市':'#a5d6a7','全期':'#90caf9'}

def make_table(phase_lbl):
    rows = ''
    for name, etf in data.items():
        ph = etf['phases'].get(phase_lbl, {})
        alphas = {s: ph.get(s,{}).get('metrics',{}).get('alpha', None) for s in STRATS}
        valid = [a for a in alphas.values() if a is not None]
        best_a = max(valid) if valid else None
        bnh = ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return', 0)
        cells = f'<td class="etf-n">{name}</td>'
        for s in STRATS:
            m = ph.get(s,{}).get('metrics',{})
            if not m: cells += '<td>—</td>'; continue
            tr_v = m['total_return']; al = m['alpha']
            is_best = best_a is not None and abs(al - best_a) < 0.05
            bg = 'background:rgba(255,215,0,.14);font-weight:700;' if is_best else ''
            ac = '#4caf50' if al >= 0 else '#ef5350'
            cells += f'<td style="{bg}"><span class="tv">{tr_v:+.1f}%</span><br><span class="av" style="color:{ac}">α{al:+.1f}%</span></td>'
        cells += f'<td class="bc">{bnh:+.1f}%</td>'
        rows += f'<tr>{cells}</tr>\n'
    return rows

# Build bar charts (alpha by phase) + line charts per ETF
charts_js = ''
for name, etf in data.items():
    sid = 'x_' + ''.join(c for c in name if c.isalnum())

    # Alpha bar chart (grouped: x=strategies, groups=phases)
    phase_series = []
    for plbl in PHASES:
        alphas = []
        for s in STRATS:
            a = etf['phases'].get(plbl,{}).get(s,{}).get('metrics',{}).get('alpha', 0)
            alphas.append(round(a,1))
        col = {'熊市':'#ef5350','牛市':'#4caf50','全期':'#90caf9'}[plbl]
        phase_series.append(f'{{name:"{plbl}",data:{json.dumps(alphas)},color:"{col}"}}')

    # Equity line (全期)
    cum_series = []
    full = etf['phases'].get('全期',{})
    dates_full = full.get('pos_v2',{}).get('dates',[])
    for s in STRATS:
        seg = full.get(s,{})
        if seg:
            lw = 2.5 if s == 'pos_v2' else 1.8
            cum_series.append(f'{{name:"{LABELS[s]}",data:{json.dumps(seg.get("cum_ret",[]))},color:"{COLORS[s]}",lineWidth:{lw}}}')
    bnh_data = full.get('pos_v2',{}).get('bnh_ret',[])
    cum_series.append(f'{{name:"BNH",data:{json.dumps(bnh_data)},color:"#888",lineWidth:1.5,dashStyle:"Dash"}}')

    strat_cats = json.dumps([LABELS[s] for s in STRATS])
    charts_js += f"""
    Highcharts.chart('{sid}_bar',{{
      chart:{{type:'column',backgroundColor:'#1a1d27',height:230}},
      title:{{text:'{name} — 各策略各阶段 Alpha',style:{{color:'#ccc',fontSize:'12px'}}}},
      xAxis:{{categories:{strat_cats},labels:{{style:{{color:'#aaa',fontSize:'10px'}}}},gridLineColor:'#1e2030'}},
      yAxis:{{title:{{text:'Alpha(%)',style:{{color:'#888'}}}},labels:{{style:{{color:'#888',fontSize:'10px'}},format:'{{value}}%'}},
        gridLineColor:'#1e2030',plotLines:[{{value:0,color:'#555',width:1}}]}},
      legend:{{itemStyle:{{color:'#aaa',fontSize:'10px'}}}},
      tooltip:{{valueDecimals:1,valueSuffix:'%',shared:false,
        backgroundColor:'rgba(15,17,23,.95)',borderColor:'#333',style:{{color:'#eee'}}}},
      series:[{','.join(phase_series)}],credits:{{enabled:false}},
      plotOptions:{{column:{{groupPadding:0.05,pointPadding:0.02}}}}
    }});
    Highcharts.chart('{sid}_line',{{
      chart:{{backgroundColor:'#1a1d27',height:230}},
      title:{{text:'全期累计收益',style:{{color:'#ccc',fontSize:'12px'}}}},
      xAxis:{{categories:{json.dumps(dates_full)},tickInterval:Math.floor({len(dates_full)}/7)||1,
        labels:{{style:{{color:'#888',fontSize:'10px'}},rotation:-30}},gridLineColor:'#1e2030'}},
      yAxis:{{title:{{text:'累计收益(%)',style:{{color:'#888'}}}},labels:{{style:{{color:'#888',fontSize:'10px'}},format:'{{value}}%'}},
        gridLineColor:'#1e2030',plotLines:[{{value:0,color:'#444',width:1}}]}},
      legend:{{itemStyle:{{color:'#aaa',fontSize:'10px'}}}},
      tooltip:{{shared:true,valueDecimals:1,valueSuffix:'%',backgroundColor:'rgba(15,17,23,.95)',borderColor:'#333',style:{{color:'#eee'}}}},
      series:[{','.join(cum_series)}],credits:{{enabled:false}},
      plotOptions:{{series:{{animation:false,marker:{{enabled:false}}}}}}
    }});
    """

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>扩展策略对比 — v2 vs SuperTrend / ADX+MA / MACD / Chandelier</title>
<script src="https://code.highcharts.com/highcharts.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f1117;color:#e0e0e0;padding:24px}}
h1{{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:4px}}
.sub{{color:#888;font-size:.82rem;margin-bottom:20px}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:22px}}
.card{{background:#1a1d27;border-radius:9px;padding:11px 13px;border-left:3px solid var(--c)}}
.card .cn{{font-weight:700;font-size:.83rem;color:var(--c)}}.card .cd{{font-size:.73rem;color:#888;margin-top:3px;line-height:1.5}}
.insight{{background:#1a2234;border-radius:10px;padding:14px 18px;margin-bottom:22px;font-size:.85rem;line-height:1.8;border-left:3px solid #f57c00}}
.insight strong{{color:#ffd54f}}.insight .good{{color:#a5d6a7}}.insight .bad{{color:#ef9a9a}}
.ps{{background:#1a1d27;border-radius:11px;padding:16px;margin-bottom:18px;overflow-x:auto}}
.ps h2{{font-size:.9rem;margin-bottom:10px;padding:3px 10px;border-radius:5px;display:inline-block}}
.bear-h{{background:rgba(239,83,80,.15);color:#ef9a9a}}
.bull-h{{background:rgba(76,175,80,.15);color:#a5d6a7}}
.full-h{{background:rgba(144,202,249,.1);color:#90caf9}}
table{{width:100%;border-collapse:collapse;font-size:.79rem}}
th{{background:#12151f;color:#777;padding:7px 10px;text-align:center;border-bottom:1px solid #222}}
td{{padding:6px 10px;text-align:center;border-bottom:1px solid #1e2030}}
.etf-n{{text-align:left;font-weight:600;color:#fff}}.tv{{color:#fff;font-size:.87rem}}.av{{font-size:.72rem;margin-top:1px}}.bc{{color:#888}}
tr:hover td{{background:#181c2a}}
.etf-tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0 12px}}
.etab{{padding:7px 15px;border-radius:20px;border:1px solid #2a2d3a;background:#1a1d27;color:#888;cursor:pointer;font-size:.8rem;transition:all .18s}}
.etab.active{{background:#1a73e8;border-color:#1a73e8;color:#fff}}
.panel{{display:none}}.panel.active{{display:block}}
.chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px;background:#1a1d27;border-radius:11px;padding:14px}}
</style>
</head>
<body>
<h1>扩展策略对比回测</h1>
<p class="sub">静态v2 vs SuperTrend vs ADX+MA vs MACD vs Chandelier Exit | 2023.04–2026.04 | 15bps 单边</p>

<div class="cards">
  <div class="card" style="--c:#1a73e8"><div class="cn">静态v2</div><div class="cd">WTS周线+DTS振幅<br>确认入场+非对称退出</div></div>
  <div class="card" style="--c:#00acc1"><div class="cn">SuperTrend</div><div class="cd">ATR×3 动态支撑线<br>突破上涨/跌破下跌</div></div>
  <div class="card" style="--c:#43a047"><div class="cn">ADX+MA20</div><div class="cd">ADX>20 趋势确认<br>+DI>-DI + 收盘>MA20</div></div>
  <div class="card" style="--c:#fb8c00"><div class="cn">MACD 12/26/9</div><div class="cd">MACD线>信号线<br>动量正则持仓</div></div>
  <div class="card" style="--c:#8e24aa"><div class="cn">Chandelier Exit</div><div class="cd">ATR×3 追踪止损线<br>最近22日高点-ATR×3</div></div>
</div>

<div class="insight">
<strong>诚实的评估：</strong><br>
静态v2 <span class="good">显著优势</span>：深证100(全期 α+35.9%，其次 ADX+MA -7.2%)、中证500(全期 α+21.5%)，主要靠<strong>熊市保护能力远超其他策略</strong>。<br>
静态v2 <span class="bad">明显劣势</span>：科创50全期 ADX+MA α+35.5%、MACD α+32.9%，均大幅超过v2(α+11.8%)——原因是科创50牛市涨+116%，ADX/MACD牛市少漏单。<br>
创业板所有策略全部负α，SuperTrend/ADX+MA（约-15%）是最小损伤，但没有一个能解决问题。<br>
<strong>结论：v2 不是"万能最好"，但在大/中盘稳定型ETF（深证100、中证500、沪深300熊市）是最强策略；
在高波动成长型ETF（科创50、创业板），ADX+MA或MACD在某些阶段更优。</strong>
</div>

<div class="ps"><h2 class="bear-h">熊市 2023.04–2024.09</h2>
<table><tr><th>标的</th>
{' '.join([f'<th style="color:{COLORS[s]}">{LABELS[s]}</th>' for s in STRATS])}
<th>BNH</th></tr>
{make_table("熊市")}</table></div>

<div class="ps"><h2 class="bull-h">牛市 2024.09–2026.04</h2>
<table><tr><th>标的</th>
{' '.join([f'<th style="color:{COLORS[s]}">{LABELS[s]}</th>' for s in STRATS])}
<th>BNH</th></tr>
{make_table("牛市")}</table></div>

<div class="ps"><h2 class="full-h">全期 2023.04–2026.04</h2>
<table><tr><th>标的</th>
{' '.join([f'<th style="color:{COLORS[s]}">{LABELS[s]}</th>' for s in STRATS])}
<th>BNH</th></tr>
{make_table("全期")}</table></div>

<div class="etf-tabs" id="etfTabs"></div>
<div id="etfPanels"></div>

<script>
const ETF_NAMES = {json.dumps(ETF_NAMES)};
const tabsEl=document.getElementById('etfTabs');
const panelsEl=document.getElementById('etfPanels');
ETF_NAMES.forEach((name,idx)=>{{
  const sid='x_'+name.replace(/[^a-zA-Z0-9]/g,'');
  const tab=document.createElement('button');
  tab.className='etab'+(idx===0?' active':'');
  tab.textContent=name; tab.onclick=()=>switchETF(name);
  tabsEl.appendChild(tab);
  const panel=document.createElement('div');
  panel.id='panel_'+sid;
  panel.className='panel'+(idx===0?' active':'');
  panel.innerHTML=`<div class="chart-row"><div id="${{sid}}_bar"></div><div id="${{sid}}_line"></div></div>`;
  panelsEl.appendChild(panel);
}});
function switchETF(name){{
  const sid='x_'+name.replace(/[^a-zA-Z0-9]/g,'');
  document.querySelectorAll('.etab').forEach((t,i)=>t.classList.toggle('active',ETF_NAMES[i]===name));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.getElementById('panel_'+sid).classList.add('active');
}}
window.addEventListener('load',()=>{{ {charts_js} }});
</script>
</body>
</html>'''

out = OUTPUT/'extended_strategy_comparison.html'
with open(out,'w',encoding='utf-8') as f:
    f.write(html)
print(f"saved: {out}  ({out.stat().st_size//1024} KB)")
