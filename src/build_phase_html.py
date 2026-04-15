"""生成分阶段资金对比仪表盘"""
import json
from pathlib import Path

OUTPUT = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")
with open(OUTPUT/'phase_comparison.json', encoding='utf-8') as f:
    raw = f.read()

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>熊市保本 → 牛市复利 分阶段资金对比</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--bg2:#161b22;--bg3:#21262d;--border:#30363d;
  --text:#e6edf3;--muted:#8b949e;
  --green:#3fb950;--red:#f85149;--yellow:#d29922;
  --asym:#ffa657;--bnh:#58a6ff;
}
body{background:var(--bg);color:var(--text);font-family:-apple-system,sans-serif;font-size:13px}
.hdr{background:var(--bg2);border-bottom:1px solid var(--border);padding:10px 16px}
.hdr h1{font-size:15px;font-weight:700;margin-bottom:3px}
.hdr p{font-size:10px;color:var(--muted);line-height:1.6}

.layout{display:grid;grid-template-columns:220px 1fr;height:calc(100vh - 70px)}
.side{background:var(--bg2);border-right:1px solid var(--border);overflow-y:auto}
.main{overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:8px}

.sc{padding:9px 12px;cursor:pointer;border-left:3px solid transparent;
  border-bottom:1px solid rgba(48,54,61,.35);transition:.1s}
.sc:hover{background:var(--bg3)}.sc.on{background:var(--bg3);border-left-color:#ffa657}
.sn{font-size:12px;font-weight:700;margin-bottom:4px}
.mini-bars{display:flex;gap:2px;align-items:flex-end;height:28px;margin-top:4px}
.mb{border-radius:2px 2px 0 0;min-width:18px;display:flex;align-items:flex-end;
  justify-content:center;font-size:8px;font-weight:700;color:rgba(255,255,255,.8);padding-bottom:1px}

.card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:11px}
.ct{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px}

#c-flow{width:100%;height:260px}
#c-equity-bear{width:100%;height:180px}
#c-equity-bull{width:100%;height:180px}
#c-mdd{width:100%;height:160px}

.chain-visual{display:flex;align-items:center;gap:0;padding:14px 0 8px}
.phase-box{flex:1;text-align:center;position:relative}
.phase-lbl{font-size:9px;color:var(--muted);text-transform:uppercase;margin-bottom:6px;letter-spacing:.4px}
.bar-row{display:flex;gap:6px;justify-content:center;align-items:flex-end;height:80px}
.bar-col{display:flex;flex-direction:column;align-items:center;gap:3px}
.bar-lbl{font-size:8px;color:var(--muted)}
.bar-val{font-size:10px;font-weight:700}
.bar-body{width:36px;border-radius:3px 3px 0 0;transition:height .3s}
.arrow{flex:0 0 28px;text-align:center;color:var(--border);font-size:18px;padding-bottom:28px}

.summary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.sg-box{background:var(--bg);border:1px solid var(--border);border-radius:5px;padding:8px 10px;text-align:center}
.sg-lbl{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.sg-val{font-size:14px;font-weight:700;margin-top:2px}
.sg-sub{font-size:9px;color:var(--muted);margin-top:1px}

.insight{background:var(--bg3);border-radius:6px;padding:10px 13px;font-size:11px;
  line-height:1.8;border:1px solid var(--border);margin-bottom:2px}
.insight code{background:var(--bg);padding:1px 5px;border-radius:3px;
  font-family:monospace;font-size:10px;color:#ffa657}
.good{background:rgba(63,185,80,.1);border:1px solid rgba(63,185,80,.3);
  padding:8px 12px;border-radius:5px;font-size:11px;color:#3fb950}
.warn{background:rgba(210,153,34,.1);border:1px solid rgba(210,153,34,.3);
  padding:8px 12px;border-radius:5px;font-size:11px;color:#d29922}
.bad{background:rgba(248,81,73,.1);border:1px solid rgba(248,81,73,.3);
  padding:8px 12px;border-radius:5px;font-size:11px;color:#f85149}

.all-tbl{width:100%;border-collapse:collapse;font-size:11px}
.all-tbl th{background:var(--bg3);padding:5px 8px;text-align:center;color:var(--muted);
  font-size:8px;text-transform:uppercase;border-bottom:1px solid var(--border);border-right:1px solid rgba(48,54,61,.4)}
.all-tbl th.nm{text-align:left}
.all-tbl td{padding:5px 8px;text-align:center;
  border-bottom:1px solid rgba(48,54,61,.3);border-right:1px solid rgba(48,54,61,.2)}
.all-tbl td.nm{text-align:left;font-weight:700}
.all-tbl tr:hover td{background:var(--bg3)}
.g{color:var(--green)}.r{color:var(--red)}.m{color:var(--muted)}
.winner{font-weight:800}
.sep{border-left:2px solid rgba(255,166,87,.3) !important}
</style>
</head>
<body>
<div class="hdr">
  <h1>熊市保本 → 牛市复利 · 分阶段资金对比</h1>
  <p>
    起始资金 100万 · 非对称DTS v2（新参数）vs 买入持有 · 含手续费（单边0.15%）<br>
    <span style="color:#ffa657">■</span> 非对称DTS策略 &nbsp;
    <span style="color:#58a6ff">■</span> 买入持有(BNH) &nbsp;&nbsp;
    熊市：2023-04-17 ~ 2024-09-20 &nbsp;|&nbsp; 牛市：2024-09-23 ~ 2026-04-15
  </p>
</div>

<div class="layout">
  <div class="side" id="side"></div>
  <div class="main" id="main"></div>
</div>

<script>
const D = __DATA__;
const NS = Object.keys(D);
const INIT = 1000000;
let cur = NS[0];
const C = {}, $ = id => document.getElementById(id);
const gc = id => { if(!C[id]) C[id]=echarts.init($(id),'dark'); return C[id]; };
const fmt = v => (v/10000).toFixed(1)+'万';
const fmtW = v => (v/10000).toFixed(2)+'万';
const pp = v => (v>=0?'+':'')+v.toFixed(1)+'%';
const cc = v => v>0?'g':v<0?'r':'m';

function renderSide(){
  $('side').innerHTML = NS.map(n=>{
    const ch = D[n].chain;
    const bearAsym = D[n].phases['熊市']?.asym?.metrics;
    const bearBnh  = D[n].phases['熊市']?.wts?.metrics;
    if(!ch||!bearAsym) return '';
    const advantage = ch.final_asym - ch.final_bnh;
    const color = advantage >= 0 ? '#3fb950' : '#f85149';
    const maxV = Math.max(ch.final_asym, ch.final_bnh, INIT);
    const scl = 24/maxV;
    return `<div class="sc ${n===cur?'on':''}" onclick="sel('${n}')">
      <div class="sn">${n}
        <span style="font-size:9px;padding:1px 5px;border-radius:3px;margin-left:3px;
          background:${advantage>=0?'rgba(63,185,80,.2)':'rgba(248,81,73,.15)'};
          color:${color};font-weight:600">${advantage>=0?'+':''}${fmtW(advantage)}</span>
      </div>
      <div style="font-size:9px;color:var(--muted);margin-bottom:3px">
        熊市α <span class="g">${pp(bearAsym.alpha)}</span>
        &nbsp;|&nbsp; 最终策略 <b style="color:#ffa657">${fmt(ch.final_asym)}</b>
        vs BNH <b style="color:#58a6ff">${fmt(ch.final_bnh)}</b>
      </div>
      <div class="mini-bars">
        <div class="mb" style="background:#555;height:${INIT*scl}px">100</div>
        <div class="mb" style="background:#ffa657;height:${ch.bear_end_asym*scl}px">${(ch.bear_end_asym/10000).toFixed(0)}</div>
        <div class="mb" style="background:#58a6ff;height:${ch.bear_end_bnh*scl}px">${(ch.bear_end_bnh/10000).toFixed(0)}</div>
        <div style="width:6px"></div>
        <div class="mb" style="background:#ffa657;height:${ch.final_asym*scl}px">${(ch.final_asym/10000).toFixed(0)}</div>
        <div class="mb" style="background:#58a6ff;height:${ch.final_bnh*scl}px">${(ch.final_bnh/10000).toFixed(0)}</div>
      </div>
      <div style="display:flex;gap:4px;margin-top:2px">
        <div style="font-size:8px;color:var(--muted);width:24px;text-align:center">初</div>
        <div style="font-size:8px;color:#ffa657;width:20px;text-align:center">策</div>
        <div style="font-size:8px;color:#58a6ff;width:20px;text-align:center">BNH</div>
        <div style="width:6px"></div>
        <div style="font-size:8px;color:#ffa657;width:20px;text-align:center">策</div>
        <div style="font-size:8px;color:#58a6ff;width:20px;text-align:center">BNH</div>
      </div>
    </div>`;
  }).join('');
}

function renderMain(n){
  const ed = D[n];
  const ch = ed.chain;
  const bear = ed.phases['熊市'];
  const bull_fixed = ed.phases['牛市'];
  const full = ed.phases['全程'];
  if(!ch||!bear) return;

  const bearAlpha = bear.asym.metrics.alpha;
  const finalAdv = ch.final_asym - ch.final_bnh;
  const recover_bnh = ch.bear_end_bnh > 0 ? ((ch.final_bnh/ch.bear_end_bnh - 1)*100) : 0;
  const recover_asym = ch.bear_end_asym > 0 ? ((ch.final_asym/ch.bear_end_asym - 1)*100) : 0;
  const bull_ret_bnh = bull_fixed?.wts?.metrics?.bnh_return ?? 0;

  let bannerClass = finalAdv >= 10000 ? 'good' : finalAdv >= 0 ? 'good' : 'bad';
  let bannerText;
  if(finalAdv >= 10000)
    bannerText = `✓ 熊市少亏 <b>${pp(bearAlpha)}</b> 的超额，复利到最终多赚 <b>${fmtW(finalAdv)}</b>（${fmt(ch.final_asym)} vs ${fmt(ch.final_bnh)}）`;
  else if(finalAdv >= 0)
    bannerText = `→ 最终策略 ${fmt(ch.final_asym)} vs BNH ${fmt(ch.final_bnh)}，小幅优势 ${fmtW(finalAdv)}`;
  else
    bannerText = `⚠ ${n} 牛市涨幅过猛（BNH +${pp(bull_ret_bnh)}），策略最终落后 BNH ${fmtW(Math.abs(finalAdv))}（持仓时间短，错失急涨日）`;

  $('main').innerHTML = `
    <div class="${bannerClass}">${bannerText}</div>

    <div class="card">
      <div class="ct">分阶段资金流：100万起，熊市 → 牛市（链式复利）</div>
      <div id="c-flow"></div>
    </div>

    <div class="card">
      <div class="ct">关键数字：为什么熊市少亏很重要</div>
      <div class="summary-grid">
        <div class="sg-box" style="border-color:#ffa65730">
          <div class="sg-lbl" style="color:#ffa657">熊市末 策略资金</div>
          <div class="sg-val ${cc(bear.asym.metrics.total_return)}">${fmt(ch.bear_end_asym)}</div>
          <div class="sg-sub">收益 ${pp(bear.asym.metrics.total_return)} · α ${pp(bear.asym.metrics.alpha)}</div>
        </div>
        <div class="sg-box" style="border-color:#58a6ff30">
          <div class="sg-lbl" style="color:#58a6ff">熊市末 BNH资金</div>
          <div class="sg-val ${cc(bear.wts.metrics.bnh_return)}">${fmt(ch.bear_end_bnh)}</div>
          <div class="sg-sub">收益 ${pp(bear.wts.metrics.bnh_return)}</div>
        </div>
        <div class="sg-box" style="border-color:#3fb95030">
          <div class="sg-lbl" style="color:#3fb950">熊市阶段 超额保留</div>
          <div class="sg-val g">+${fmt(ch.bear_end_asym - ch.bear_end_bnh)}</div>
          <div class="sg-sub">策略多保住这些本金进入牛市</div>
        </div>
        <div class="sg-box" style="border-color:#ffa65730">
          <div class="sg-lbl" style="color:#ffa657">牛市末 策略资金（链式）</div>
          <div class="sg-val ${cc(ch.final_asym - INIT)}">${fmt(ch.final_asym)}</div>
          <div class="sg-sub">牛市涨幅 ${pp(recover_asym)}</div>
        </div>
        <div class="sg-box" style="border-color:#58a6ff30">
          <div class="sg-lbl" style="color:#58a6ff">牛市末 BNH资金（链式）</div>
          <div class="sg-val ${cc(ch.final_bnh - INIT)}">${fmt(ch.final_bnh)}</div>
          <div class="sg-sub">牛市涨幅 ${pp(recover_bnh)}</div>
        </div>
        <div class="sg-box" style="${finalAdv>=0?'border-color:#3fb95030;':'border-color:#f8514930;'}">
          <div class="sg-lbl" style="color:${finalAdv>=0?'#3fb950':'#f85149'}">最终资金差距</div>
          <div class="sg-val ${cc(finalAdv)}">${finalAdv>=0?'+':''}${fmtW(finalAdv)}</div>
          <div class="sg-sub">策略 vs BNH，全程3年</div>
        </div>
      </div>
    </div>

    <div class="insight">
      <b style="color:#ffa657">复利逻辑</b>：
      熊市策略从 <b>${fmt(INIT)}</b> 跌至 <b>${fmt(ch.bear_end_asym)}</b>（亏 ${pp(bear.asym.metrics.total_return)}）；
      BNH从 <b>${fmt(INIT)}</b> 跌至 <b>${fmt(ch.bear_end_bnh)}</b>（亏 ${pp(bear.wts.metrics.bnh_return)}）。
      两者基数相差 <code>${fmt(ch.bear_end_asym - ch.bear_end_bnh)}</code>。
      牛市同样的百分比涨幅作用于不同本金：
      策略本金大 → 绝对收益更多。
      <span class="m">即使牛市百分比相同，最终金额也更高。</span>
    </div>

    <div class="g2">
      <div class="card"><div class="ct">熊市阶段累计收益曲线（各自100万起）</div><div id="c-equity-bear"></div></div>
      <div class="card"><div class="ct">牛市阶段累计收益曲线（各自100万起，非链式）</div><div id="c-equity-bull"></div></div>
    </div>

    <div class="card">
      <div class="ct">最大回撤对比（全程）</div>
      <div id="c-mdd"></div>
    </div>

    <div class="card">
      <div class="ct">全ETF 分阶段汇总</div>
      <table class="all-tbl" id="sum-tbl"></table>
    </div>
  `;

  // === Flow chart: grouped bar ===
  const phases_bar = ['初始(100万)', '熊市末', '牛市末(链式)'];
  const asym_vals = [INIT, ch.bear_end_asym, ch.final_asym].map(v=>+(v/10000).toFixed(1));
  const bnh_vals  = [INIT, ch.bear_end_bnh, ch.final_bnh].map(v=>+(v/10000).toFixed(1));
  gc('c-flow').setOption({
    backgroundColor:'transparent',
    tooltip:{trigger:'axis',formatter(p){
      return p.map(s=>`${s.marker}${s.seriesName}: <b>${s.value}万</b>`).join('<br>');
    }},
    legend:{top:2,textStyle:{color:'#8b949e',fontSize:9}},
    grid:{top:30,bottom:28,left:52,right:14},
    xAxis:{type:'category',data:phases_bar,axisLabel:{color:'#8b949e',fontSize:10}},
    yAxis:{name:'万元',splitLine:{lineStyle:{color:'#21262d'}},
      axisLabel:{color:'#8b949e',fontSize:9,formatter:v=>v+'万'},
      min: v => Math.floor(v.min*0.9)},
    series:[
      {name:'非对称策略',type:'bar',barMaxWidth:42,data:asym_vals,
        itemStyle:{color(p){return p.dataIndex===2?'#ffa657':p.dataIndex===1?'#cc7a30':'#888';}},
        label:{show:true,position:'top',color:'#ffa657',fontSize:10,formatter:'{c}万'}},
      {name:'BNH',type:'bar',barMaxWidth:42,data:bnh_vals,
        itemStyle:{color(p){return p.dataIndex===2?'#58a6ff':p.dataIndex===1?'#2a5a99':'#888';}},
        label:{show:true,position:'top',color:'#58a6ff',fontSize:10,formatter:'{c}万'}},
      {name:'100万基准',type:'line',data:[100,100,100],symbol:'none',
        lineStyle:{color:'#30363d',type:'dashed',width:1.5}},
    ],
    markLine:{silent:true}
  },true);

  // === Bear equity ===
  if(bear.asym){
    gc('c-equity-bear').setOption({
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      legend:{top:2,textStyle:{color:'#8b949e',fontSize:8}},
      grid:{top:22,bottom:20,left:42,right:8},
      xAxis:{type:'category',data:bear.asym.dates,
        axisLine:{lineStyle:{color:'#30363d'}},axisLabel:{color:'#8b949e',fontSize:7,interval:'auto'}},
      yAxis:{scale:true,splitLine:{lineStyle:{color:'#21262d'}},
        axisLabel:{color:'#8b949e',fontSize:8,formatter:v=>v+'%'}},
      series:[
        {name:'非对称策略',type:'line',data:bear.asym.cum_ret,smooth:true,symbol:'none',
          lineStyle:{color:'#ffa657',width:2.5},
          areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,
            colorStops:[{offset:0,color:'rgba(255,166,87,.2)'},{offset:1,color:'rgba(255,166,87,.02)'}]}}},
        {name:'BNH',type:'line',data:bear.asym.bnh_ret,smooth:true,symbol:'none',lineStyle:{color:'#58a6ff',width:1.5,type:'dashed'}},
      ]
    },true);
  }

  // === Bull equity (fixed start) ===
  if(bull_fixed?.asym){
    gc('c-equity-bull').setOption({
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      legend:{top:2,textStyle:{color:'#8b949e',fontSize:8}},
      grid:{top:22,bottom:20,left:42,right:8},
      xAxis:{type:'category',data:bull_fixed.asym.dates,
        axisLine:{lineStyle:{color:'#30363d'}},axisLabel:{color:'#8b949e',fontSize:7,interval:'auto'}},
      yAxis:{scale:true,splitLine:{lineStyle:{color:'#21262d'}},
        axisLabel:{color:'#8b949e',fontSize:8,formatter:v=>v+'%'}},
      series:[
        {name:'非对称策略',type:'line',data:bull_fixed.asym.cum_ret,smooth:true,symbol:'none',
          lineStyle:{color:'#ffa657',width:2}},
        {name:'BNH',type:'line',data:bull_fixed.wts?.bnh_ret ?? bull_fixed.asym.bnh_ret,
          smooth:true,symbol:'none',lineStyle:{color:'#58a6ff',width:1.5,type:'dashed'}},
      ]
    },true);
  }

  // === MDD bar ===
  const pids = ['全程','熊市','牛市'];
  gc('c-mdd').setOption({
    backgroundColor:'transparent',tooltip:{},
    legend:{bottom:0,textStyle:{color:'#8b949e',fontSize:8}},
    grid:{top:8,bottom:28,left:42,right:8},
    xAxis:{type:'category',data:pids,axisLabel:{color:'#8b949e',fontSize:9}},
    yAxis:{splitLine:{lineStyle:{color:'#21262d'}},
      axisLabel:{color:'#8b949e',fontSize:8,formatter:v=>v+'%'}},
    series:[
      {name:'策略最大回撤',type:'bar',barMaxWidth:20,
        data:pids.map(p=>ed.phases[p]?.asym?.metrics?.max_drawdown??null),
        itemStyle:{color:'#cc4a30'},
        label:{show:true,position:'inside',color:'#fff',fontSize:9,formatter:'{c}%'}},
      {name:'BNH最大回撤',type:'bar',barMaxWidth:20,
        data:pids.map(p=>ed.phases[p]?.wts?.metrics?.max_drawdown??null),
        itemStyle:{color:'#1a3a6a'},
        label:{show:true,position:'inside',color:'#fff',fontSize:9,formatter:'{c}%'}},
    ]
  },true);

  // === Summary table ===
  let th = `<thead><tr>
    <th class="nm">标的</th>
    <th colspan="3" style="color:#8b949e">熊市 (2023.4~2024.9)</th>
    <th class="sep" colspan="2" style="color:#ffa657">链式末资金</th>
    <th colspan="2" style="color:#58a6ff">最终对比</th>
  </tr><tr>
    <th class="nm">起始100万</th>
    <th style="color:#ffa657">策略末</th><th style="color:#58a6ff">BNH末</th><th>α差距</th>
    <th class="sep" style="color:#ffa657">策略(万)</th><th style="color:#58a6ff">BNH(万)</th>
    <th style="color:#3fb950">差额</th><th>3年α</th>
  </tr></thead>`;
  let tb = '<tbody>';
  NS.forEach(nm=>{
    const ed2 = D[nm]; const ch2=ed2.chain;
    const b2=ed2.phases['熊市']; if(!b2||!ch2) return;
    const adv2 = ch2.final_asym - ch2.final_bnh;
    const bearAlpha2 = b2.asym.metrics.alpha;
    const fullAlpha2 = ed2.phases['全程']?.asym?.metrics?.alpha ?? null;
    tb += `<tr${nm===cur?' style="background:var(--bg3)"':''}>
      <td class="nm" onclick="sel('${nm}')" style="cursor:pointer">${nm}</td>
      <td class="${cc(b2.asym.metrics.total_return)}">${fmt(ch2.bear_end_asym)}</td>
      <td class="${cc(b2.wts.metrics.bnh_return)}">${fmt(ch2.bear_end_bnh)}</td>
      <td class="g">${fmt(ch2.bear_end_asym - ch2.bear_end_bnh)}</td>
      <td class="sep ${cc(ch2.final_asym-INIT)} winner">${(ch2.final_asym/10000).toFixed(2)}</td>
      <td class="${cc(ch2.final_bnh-INIT)}">${(ch2.final_bnh/10000).toFixed(2)}</td>
      <td class="${cc(adv2)} winner" style="${adv2>=0?'color:#3fb950':'color:#f85149'}">${adv2>=0?'+':''}${fmtW(adv2)}</td>
      <td class="${fullAlpha2!==null?cc(fullAlpha2):'m'}">${fullAlpha2!==null?pp(fullAlpha2):'--'}</td>
    </tr>`;
  });
  tb += '</tbody>';
  $('sum-tbl').innerHTML = th + tb;
}

function sel(n){cur=n;renderSide();renderMain(n);}
renderSide(); sel(cur);
window.addEventListener('resize',()=>Object.values(C).forEach(c=>c.resize()));
</script>
</body>
</html>'''.replace('__DATA__', raw)

out = OUTPUT / 'phase_comparison.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"HTML生成: {out}  ({out.stat().st_size//1024} KB)")
