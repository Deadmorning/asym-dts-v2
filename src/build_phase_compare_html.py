#!/usr/bin/env python3
import json
from pathlib import Path

OUTPUT = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")
with open(OUTPUT/'phase_compare_results.json','r',encoding='utf-8') as f:
    data = json.load(f)

ETF_NAMES = list(data.keys())
STRATS = ['pos_v2','pos_dual_ma','pos_multi_tf','pos_turtle']
LABELS = {'pos_v2':'静态v2','pos_dual_ma':'双均线 MA5/20','pos_multi_tf':'多周期共振','pos_turtle':'海龟CTA'}
COLORS = {'pos_v2':'#1a73e8','pos_dual_ma':'#e53935','pos_multi_tf':'#f57c00','pos_turtle':'#7b1fa2'}
PHASES = ['熊市','牛市','全期']
PHASE_COLORS = {'熊市':'#ef5350','牛市':'#4caf50','全期':'#90caf9'}

# Build alpha heatmap table for each phase
def phase_table(phase_lbl):
    rows = ''
    for name, etf in data.items():
        ph = etf['phases'].get(phase_lbl, {})
        if not ph: continue
        alphas = {s: ph.get(s,{}).get('metrics',{}).get('alpha', None) for s in STRATS}
        valid  = [a for a in alphas.values() if a is not None]
        best_a = max(valid) if valid else None
        bnh    = ph.get('pos_v2',{}).get('metrics',{}).get('bnh_return', 0)

        cells = f'<td class="etf-n">{name}</td>'
        for s in STRATS:
            m = ph.get(s,{}).get('metrics',{})
            if not m: cells += '<td>—</td>'; continue
            tr = m['total_return']; al = m['alpha']
            is_best = best_a is not None and abs(al - best_a) < 0.05
            bg = ''
            if is_best: bg = 'background:rgba(255,215,0,.13);font-weight:700'
            ac = '#4caf50' if al >= 0 else '#ef5350'
            cells += f'<td style="{bg}"><span class="tr">{tr:+.1f}%</span><br><span class="al" style="color:{ac}">α{al:+.1f}%</span></td>'
        cells += f'<td class="bnh-c">{bnh:+.1f}%</td>'
        rows += f'<tr>{cells}</tr>\n'
    return rows

# Charts: one per ETF — 3-phase alpha bar chart
charts_js = ''
for name, etf in data.items():
    sid = 'c_' + ''.join(c for c in name if c.isalnum())
    # bar chart: x=phases, series=strategies, value=alpha
    series = []
    for s in STRATS:
        alphas = []
        for ph in PHASES:
            a = etf['phases'].get(ph,{}).get(s,{}).get('metrics',{}).get('alpha', None)
            alphas.append(round(a,1) if a is not None else 0)
        series.append(f'{{name:"{LABELS[s]}",data:{json.dumps(alphas)},color:"{COLORS[s]}",pointPadding:0.05}}')

    # also build cumulative equity chart per phase
    cum_series = []
    for s in STRATS:
        full = etf['phases'].get('全期',{}).get(s,{})
        if full:
            cum_series.append(f'{{name:"{LABELS[s]}",data:{json.dumps(full.get("cum_ret",[]))},color:"{COLORS[s]}",lineWidth:{"2.5" if s=="pos_v2" else "1.8"}}}')
    bnh_full = etf['phases'].get('全期',{}).get('pos_v2',{})
    if bnh_full:
        cum_series.append(f'{{name:"BNH",data:{json.dumps(bnh_full.get("bnh_ret",[]))},color:"#888",lineWidth:1.5,dashStyle:"Dash"}}')
    dates_full = bnh_full.get('dates',[]) if bnh_full else []

    charts_js += f"""
    // Bar chart: alpha by phase
    Highcharts.chart('{sid}_bar', {{
      chart:{{type:'bar',backgroundColor:'#1a1d27',height:220}},
      title:{{text:'{name} — 各阶段 Alpha',style:{{color:'#ccc',fontSize:'12px'}}}},
      xAxis:{{categories:{json.dumps(PHASES)},labels:{{style:{{color:'#aaa'}}}},gridLineColor:'#1e2030'}},
      yAxis:{{title:{{text:'Alpha (%)',style:{{color:'#888'}}}},labels:{{style:{{color:'#888'}},format:'{{value}}%'}},
        gridLineColor:'#1e2030',plotLines:[{{value:0,color:'#555',width:1}}]}},
      legend:{{itemStyle:{{color:'#aaa',fontSize:'10px'}}}},
      tooltip:{{valueDecimals:1,valueSuffix:'%',backgroundColor:'rgba(15,17,23,.95)',borderColor:'#333',style:{{color:'#eee'}}}},
      series:[{','.join(series)}],
      credits:{{enabled:false}},plotOptions:{{bar:{{groupPadding:0.1}}}}
    }});
    // Equity curve
    Highcharts.chart('{sid}_line', {{
      chart:{{backgroundColor:'#1a1d27',height:280}},
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
<title>四策略分阶段对比 — 熊市/牛市/全期</title>
<script src="https://code.highcharts.com/highcharts.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#0f1117;color:#e0e0e0;padding:24px}}
h1{{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:4px}}
.sub{{color:#888;font-size:.82rem;margin-bottom:22px}}

/* insight */
.insight{{background:#1a2234;border-radius:10px;padding:16px 20px;margin-bottom:24px;font-size:.86rem;line-height:1.8;border-left:3px solid #f57c00}}
.insight strong{{color:#ffd54f}}
.insight .phase-tag{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:.76rem;font-weight:600;margin:0 3px}}
.bear{{background:rgba(239,83,80,.2);color:#ef9a9a}}.bull{{background:rgba(76,175,80,.2);color:#a5d6a7}}

/* phase tables */
.phase-section{{background:#1a1d27;border-radius:12px;padding:18px;margin-bottom:22px;overflow-x:auto}}
.phase-section h2{{font-size:.95rem;margin-bottom:12px;padding:4px 10px;border-radius:6px;display:inline-block}}
.bear-h{{background:rgba(239,83,80,.15);color:#ef9a9a}}
.bull-h{{background:rgba(76,175,80,.15);color:#a5d6a7}}
.full-h{{background:rgba(144,202,249,.1);color:#90caf9}}
.st{{width:100%;border-collapse:collapse;font-size:.8rem}}
.st th{{background:#12151f;color:#777;padding:7px 12px;text-align:center;border-bottom:1px solid #222}}
.st td{{padding:7px 12px;text-align:center;border-bottom:1px solid #1e2030}}
.etf-n{{text-align:left;font-weight:600;color:#fff}}
.tr{{color:#fff;font-size:.88rem}}
.al{{font-size:.73rem;margin-top:1px}}
.bnh-c{{color:#888;font-size:.82rem}}
.st tr:hover td{{background:#181c2a}}

/* ETF detail */
.etf-tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 14px}}
.etab{{padding:7px 15px;border-radius:20px;border:1px solid #2a2d3a;background:#1a1d27;color:#888;cursor:pointer;font-size:.8rem;transition:all .18s}}
.etab.active{{background:#1a73e8;border-color:#1a73e8;color:#fff}}
.panel{{display:none}}.panel.active{{display:block}}
.chart-row{{display:grid;grid-template-columns:1fr 1.6fr;gap:14px;background:#1a1d27;border-radius:12px;padding:14px}}
</style>
</head>
<body>
<h1>四策略分阶段对比</h1>
<p class="sub">熊市 (2023.04–2024.09) · 牛市 (2024.09–2026.04) · 全期 | 手续费 15bps 单边</p>

<div class="insight">
<strong>核心发现：</strong><br>
<span class="phase-tag bear">熊市</span> 四种策略<strong>全部都有正 Alpha</strong>，都能有效保护资本。
静态v2 在科创50(α+44.7%)、深证100(α+27%)整体最佳；
海龟CTA 在上证50(α+17.2%)、沪深300(α+18.1%)稍占优；
多周期共振在创业板(α+30.6%)、中证500(α+25.1%)表现意外突出（慢信号在熊市反而减少无效交易）。<br><br>
<span class="phase-tag bull">牛市</span> 四种策略<strong>全部都是负 Alpha</strong>——没有一个策略能跑赢 BNH。
这证明策略的价值不在牛市赚超额，而在熊市少亏。
在相对比较中，静态v2 仍是牛市跑赢最多的策略（上证50 α-0.2% 接近 BNH，中证500 α-12% 在四策略最小损耗）。
</div>

<!-- Phase tables -->
<div class="phase-section">
<h2 class="bear-h">熊市阶段 2023.04 — 2024.09（黄金底色 = 该ETF最高Alpha）</h2>
<table class="st">
<tr><th>标的</th><th style="color:{COLORS["pos_v2"]}">{LABELS["pos_v2"]}</th>
<th style="color:{COLORS["pos_dual_ma"]}">{LABELS["pos_dual_ma"]}</th>
<th style="color:{COLORS["pos_multi_tf"]}">{LABELS["pos_multi_tf"]}</th>
<th style="color:{COLORS["pos_turtle"]}">{LABELS["pos_turtle"]}</th><th>BNH</th></tr>
{phase_table("熊市")}
</table>
</div>

<div class="phase-section">
<h2 class="bull-h">牛市阶段 2024.09 — 2026.04（黄金底色 = 该ETF最高Alpha，但全部为负）</h2>
<table class="st">
<tr><th>标的</th><th style="color:{COLORS["pos_v2"]}">{LABELS["pos_v2"]}</th>
<th style="color:{COLORS["pos_dual_ma"]}">{LABELS["pos_dual_ma"]}</th>
<th style="color:{COLORS["pos_multi_tf"]}">{LABELS["pos_multi_tf"]}</th>
<th style="color:{COLORS["pos_turtle"]}">{LABELS["pos_turtle"]}</th><th>BNH</th></tr>
{phase_table("牛市")}
</table>
</div>

<div class="phase-section">
<h2 class="full-h">全期汇总 2023.04 — 2026.04</h2>
<table class="st">
<tr><th>标的</th><th style="color:{COLORS["pos_v2"]}">{LABELS["pos_v2"]}</th>
<th style="color:{COLORS["pos_dual_ma"]}">{LABELS["pos_dual_ma"]}</th>
<th style="color:{COLORS["pos_multi_tf"]}">{LABELS["pos_multi_tf"]}</th>
<th style="color:{COLORS["pos_turtle"]}">{LABELS["pos_turtle"]}</th><th>BNH</th></tr>
{phase_table("全期")}
</table>
</div>

<!-- ETF drill-down -->
<div class="etf-tabs" id="etfTabs"></div>
<div id="etfPanels"></div>

<script>
const ETF_NAMES = {json.dumps(ETF_NAMES)};
const tabsEl = document.getElementById('etfTabs');
const panelsEl = document.getElementById('etfPanels');

ETF_NAMES.forEach((name, idx) => {{
  const sid = 'c_' + name.replace(/[^a-zA-Z0-9]/g,'');
  const tab = document.createElement('button');
  tab.className = 'etab' + (idx===0?' active':'');
  tab.textContent = name;
  tab.onclick = () => switchETF(name);
  tabsEl.appendChild(tab);

  const panel = document.createElement('div');
  panel.id = 'panel_' + sid;
  panel.className = 'panel' + (idx===0?' active':'');
  panel.innerHTML = `<div class="chart-row">
    <div id="${{sid}}_bar"></div>
    <div id="${{sid}}_line"></div>
  </div>`;
  panelsEl.appendChild(panel);
}});

function switchETF(name) {{
  const sid = 'c_' + name.replace(/[^a-zA-Z0-9]/g,'');
  document.querySelectorAll('.etab').forEach((t,i) => t.classList.toggle('active', ETF_NAMES[i]===name));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel_'+sid).classList.add('active');
}}

window.addEventListener('load', () => {{
  {charts_js}
}});
</script>
</body>
</html>'''

out = OUTPUT/'phase_strategy_comparison.html'
with open(out,'w',encoding='utf-8') as f:
    f.write(html)
print(f"saved: {out}  ({out.stat().st_size//1024} KB)")
