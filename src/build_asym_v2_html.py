"""非对称DTS v1 vs v2 参数优化对比仪表盘"""
import json
from pathlib import Path

OUTPUT = Path("/home/node/a0/workspace/9f6b0b84-8364-43ba-9e79-f77b9e0902c7/workspace/outputs")
with open(OUTPUT/'asym_v2_results.json', encoding='utf-8') as f:
    raw = f.read()

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>非对称DTS v1 vs v2 参数优化</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--bg2:#161b22;--bg3:#21262d;--border:#30363d;
  --text:#e6edf3;--muted:#8b949e;
  --green:#3fb950;--red:#f85149;--yellow:#d29922;
  --v2:#ffa657;--v2c:#58a6ff;--v1:#8b949e;--wts:#555;--bnh:#30363d;
}
body{background:var(--bg);color:var(--text);font-family:-apple-system,sans-serif;font-size:13px}
.hdr{background:var(--bg2);border-bottom:1px solid var(--border);padding:9px 16px;
  display:flex;align-items:center;justify-content:space-between}
.hdr h1{font-size:14px;font-weight:700}
.leg{display:flex;gap:10px;font-size:10px;color:var(--muted)}
.li{display:flex;align-items:center;gap:4px}
.ld{width:20px;height:3px;border-radius:2px}

.layout{display:grid;grid-template-columns:232px 1fr;height:calc(100vh - 44px)}
.side{background:var(--bg2);border-right:1px solid var(--border);overflow-y:auto}
.main{overflow-y:auto;padding:10px;display:flex;flex-direction:column;gap:8px}

.sc{padding:9px 12px;cursor:pointer;border-left:3px solid transparent;
  border-bottom:1px solid rgba(48,54,61,.35);transition:.1s}
.sc:hover{background:var(--bg3)}.sc.on{background:var(--bg3);border-left-color:#ffa657}
.sn{font-size:12px;font-weight:700;margin-bottom:5px}
.sg{display:grid;grid-template-columns:repeat(3,1fr);gap:3px}
.si{background:var(--bg3);border-radius:3px;padding:3px 4px;text-align:center}
.sl{font-size:8px;color:var(--muted)}.sv{font-size:10px;font-weight:700}

.card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:11px}
.ct{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}

#c-eq-all{width:100%;height:240px}
#c-alpha-bar{width:100%;height:200px}
#c-trades-bar{width:100%;height:160px}
.mini-eq{width:100%;height:130px}

.krow{display:flex;gap:5px;flex-wrap:wrap}
.kc{flex:1;min-width:90px;background:var(--bg);border:1px solid var(--border);
  border-radius:5px;padding:7px 10px}
.kl{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.kv{font-size:15px;font-weight:700;margin-top:1px}
.ks{font-size:9px;color:var(--muted);margin-top:1px}

.ptbl{width:100%;border-collapse:collapse;font-size:11px}
.ptbl th{background:var(--bg3);padding:5px 8px;text-align:center;color:var(--muted);
  font-size:8px;text-transform:uppercase;border-bottom:1px solid var(--border);
  border-right:1px solid rgba(48,54,61,.4)}
.ptbl th.nm{text-align:left}.ptbl td{padding:4px 8px;text-align:center;
  border-bottom:1px solid rgba(48,54,61,.3);border-right:1px solid rgba(48,54,61,.2)}
.ptbl td.nm{text-align:left;font-weight:700;font-size:10px}
.ptbl tr:hover td{background:var(--bg3)}
.ptbl .sub{color:var(--muted);font-size:9px}
.winner{font-weight:700}

.improve-tag{font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600;margin-left:4px}
.logic{background:var(--bg3);border-radius:6px;padding:10px 13px;font-size:11px;
  line-height:1.8;border:1px solid var(--border)}
.logic code{background:var(--bg);padding:1px 5px;border-radius:3px;
  font-family:monospace;font-size:10px;color:#ffa657}
.warn{background:rgba(210,153,34,.1);border:1px solid rgba(210,153,34,.3);
  padding:7px 11px;border-radius:5px;font-size:10px;color:#d29922}
.good{background:rgba(63,185,80,.1);border:1px solid rgba(63,185,80,.3);
  padding:7px 11px;border-radius:5px;font-size:10px;color:#3fb950}

.g{color:var(--green)}.r{color:var(--red)}.m{color:var(--muted)}
.b{color:var(--v2c)}.o{color:var(--v2)}
</style>
</head>
<body>
<div class="hdr">
  <div>
    <h1>非对称DTS v1 → v2 参数优化对比</h1>
    <div style="font-size:10px;color:var(--muted);margin-top:2px">
      v1=对称DTS优化参数 · v2=非对称专项优化参数 · v2确认=v2参数+新多头周需DTS确认入场
    </div>
  </div>
  <div class="leg">
    <div class="li"><div class="ld" style="background:var(--v2)"></div>v2新参数</div>
    <div class="li"><div class="ld" style="background:var(--v2c)"></div>v2确认版</div>
    <div class="li"><div class="ld" style="background:var(--v1)"></div>v1旧参数</div>
    <div class="li"><div class="ld" style="background:#3fb950"></div>纯WTS</div>
    <div class="li"><div class="ld" style="background:#444;border:1px dashed #777"></div>BNH</div>
  </div>
</div>

<div class="layout">
  <div class="side" id="side"></div>
  <div class="main" id="main"></div>
</div>

<script>
const D = __DATA__;
const NS = Object.keys(D);
const STRATS = [
  {k:'pos_asym_new',   l:'v2新参数',  c:'#ffa657'},
  {k:'pos_asym_c_new', l:'v2确认版',  c:'#58a6ff'},
  {k:'pos_asym_old',   l:'v1旧参数',  c:'#8b949e'},
  {k:'pos_wts',        l:'纯WTS',     c:'#3fb950'},
];
const PIDS    = ['全程','P1','P2','P3'];
const PLABELS = {全程:'全程(3年)',P1:'P1: 2025年1月~8月',P2:'P2: 2025年8月~2026年1月',P3:'P3: 2025年8月~2026年3月'};
const PCOLS   = {全程:'#8b949e',P1:'#58a6ff',P2:'#3fb950',P3:'#ffa657'};
let cur = NS[0];
const C={}, $=id=>document.getElementById(id);
const gc=id=>{if(!C[id])C[id]=echarts.init($(id),'dark');return C[id];};
const p2=v=>(v>=0?'+':'')+Number(v).toFixed(2)+'%';
const p1=v=>(v>=0?'+':'')+Number(v).toFixed(1)+'%';
const cc=v=>v>0?'g':v<0?'r':'m';

function renderSide(){
  $('side').innerHTML = NS.map(n=>{
    const full=D[n].periods['全程'];
    const aOld = full?.pos_asym_old?.metrics?.alpha??0;
    const aNew = full?.pos_asym_new?.metrics?.alpha??0;
    const aCon = full?.pos_asym_c_new?.metrics?.alpha??0;
    const imp = aNew - aOld;
    const pc = D[n].params_changed;
    return `<div class="sc ${n===cur?'on':''}" onclick="sel('${n}')">
      <div class="sn">${n}
        ${pc?`<span class="improve-tag" style="background:${imp>0?'rgba(63,185,80,.2)':'rgba(248,81,73,.15)'};color:${imp>0?'#3fb950':'#f85149'}">${imp>0?'α+'+imp.toFixed(1)+'%':'↓'}</span>`:
        `<span class="improve-tag" style="background:rgba(139,148,158,.15);color:var(--muted)">参数不变</span>`}
      </div>
      <div style="font-size:9px;color:var(--muted);margin-bottom:4px">
        旧: SAME=${D[n].old_params.same}/REV=${D[n].old_params.rev}
        ${pc?` → 新: SAME=${D[n].new_params.same}/REV=${D[n].new_params.rev}`:''}
      </div>
      <div class="sg">
        <div class="si" style="border:1px solid #ffa65730">
          <div class="sl" style="color:#ffa657">v2新参</div>
          <div class="sv ${cc(aNew)}">${p1(aNew)}</div>
        </div>
        <div class="si" style="border:1px solid #58a6ff30">
          <div class="sl" style="color:#58a6ff">v2确认</div>
          <div class="sv ${cc(aCon)}">${p1(aCon)}</div>
        </div>
        <div class="si">
          <div class="sl">v1旧参</div>
          <div class="sv ${cc(aOld)}">${p1(aOld)}</div>
        </div>
      </div>
      <div style="font-size:9px;color:var(--muted);margin-top:3px">
        BNH ${p2(full?.pos_wts?.metrics?.bnh_return??0)}
      </div>
    </div>`;
  }).join('');
}

function renderMain(n){
  const ed=D[n];
  const full=ed.periods['全程'];
  const aOld = full?.pos_asym_old?.metrics?.alpha??0;
  const aNew = full?.pos_asym_new?.metrics?.alpha??0;
  const imp = aNew - aOld;
  const pc = ed.params_changed;

  let banner = '';
  if(pc && imp > 3)
    banner = `<div class="good">✓ 参数从 SAME=${ed.old_params.same}/REV=${ed.old_params.rev} → SAME=${ed.new_params.same}/REV=${ed.new_params.rev}，3年超额α改善 <b>+${imp.toFixed(1)}%</b>（${p1(aOld)} → <b>${p1(aNew)}</b>）</div>`;
  else if(pc && imp <= 0)
    banner = `<div class="warn">⚠ 参数调整后效果改善有限（α ${p1(aOld)} → ${p1(aNew)}），该ETF对参数不敏感</div>`;
  else if(!pc)
    banner = `<div class="warn">⚠ ${n} 参数与旧版相同，网格搜索未找到更优参数（α=${p1(aNew)}）</div>`;
  else
    banner = `<div class="warn">参数变化：SAME=${ed.old_params.same}/REV=${ed.old_params.rev} → SAME=${ed.new_params.same}/REV=${ed.new_params.rev}，改善 ${p1(imp)}</div>`;

  $('main').innerHTML = `
    ${banner}
    <div class="logic">
      <b style="color:#ffa657">v2 优化要点</b>：
      原始参数为<b>对称DTS</b>的优化结果，非对称策略的出场灵敏度不同 —
      非对称出场依赖 <code>DTS=0</code> 触发，需要更高的 <code>REV</code> 阈值过滤掉反转噪声，避免弱势日频繁出场 &nbsp;|&nbsp;
      <b style="color:#58a6ff">v2确认版</b>：新多头周入场前需 <code>dts_s=1</code>，消除"进场当日即遇坏消息"的1天亏损交易
    </div>
    <div class="krow">${[...STRATS, {k:'bnh', l:'BNH', c:'#555'}].map(s=>{
      if(s.k==='bnh'){
        const bnh=full?.pos_wts?.metrics?.bnh_return??0;
        return `<div class="kc"><div class="kl m">BNH</div><div class="kv ${cc(bnh)}">${p2(bnh)}</div><div class="ks">买入持有</div></div>`;
      }
      const r=full?.[s.k]; if(!r)return '';
      const m=r.metrics;
      return `<div class="kc" style="border-color:${s.c}30">
        <div class="kl" style="color:${s.c}">${s.l}</div>
        <div class="kv ${cc(m.alpha)}">${p2(m.alpha)}</div>
        <div class="ks">收益${p2(m.total_return)} · 夏普${m.sharpe} · T=${m.n_trades}笔</div>
      </div>`;
    }).join('')}</div>
    <div class="card"><div class="ct">全程累计收益曲线</div><div id="c-eq-all"></div></div>
    <div class="g2">
      <div class="card"><div class="ct">各阶段超额α对比</div><div id="c-alpha-bar"></div></div>
      <div class="card"><div class="ct">全程交易笔数 & 持多天比</div><div id="c-trades-bar"></div></div>
    </div>
    <div class="g3">${['P1','P2','P3'].map(p=>{
      const pr=ed.periods[p]; if(!pr) return '';
      return `<div class="card" style="border-color:${PCOLS[p]}25">
        <div class="ct" style="color:${PCOLS[p]}">${PLABELS[p]}</div>
        <div id="c-mini-${p.toLowerCase()}" class="mini-eq"></div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:3px;margin-top:6px">
          ${STRATS.slice(0,3).map(s=>{const r=pr[s.k]; if(!r)return '';
            const m=r.metrics;
            return `<div style="text-align:center">
              <div style="font-size:8px;color:${s.c}">${s.l}</div>
              <div style="font-size:11px;font-weight:700" class="${cc(m.alpha)}">${p1(m.alpha)}</div>
              <div style="font-size:9px;color:var(--muted)">${p1(m.total_return)}</div>
            </div>`;
          }).join('')}
        </div>
      </div>`;
    }).join('')}</div>
    <div class="card">
      <div class="ct">全ETF × 全阶段 超额α（v2新参 / v2确认 / v1旧参 / BNH）</div>
      <table class="ptbl" id="tbl"></table>
    </div>
  `;

  // equity chart
  if(full?.pos_asym_new){
    gc('c-eq-all').setOption({
      backgroundColor:'transparent',
      tooltip:{trigger:'axis'},
      legend:{top:2,textStyle:{color:'#8b949e',fontSize:9}},
      grid:{top:26,bottom:22,left:50,right:46},
      xAxis:{type:'category',data:full.pos_asym_new.dates,
        axisLine:{lineStyle:{color:'#30363d'}},axisLabel:{color:'#8b949e',fontSize:8,interval:'auto'}},
      yAxis:{scale:true,splitLine:{lineStyle:{color:'#21262d'}},
        axisLabel:{color:'#8b949e',fontSize:8,formatter:v=>v+'%'}},
      series:[
        {name:'v2新参数',type:'line',data:full.pos_asym_new.cum_ret,smooth:true,symbol:'none',
          lineStyle:{color:'#ffa657',width:2.5},
          areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,
            colorStops:[{offset:0,color:'rgba(255,166,87,.2)'},{offset:1,color:'rgba(255,166,87,.02)'}]}}},
        {name:'v2确认版',type:'line',data:full.pos_asym_c_new.cum_ret,smooth:true,symbol:'none',lineStyle:{color:'#58a6ff',width:1.5}},
        {name:'v1旧参数',type:'line',data:full.pos_asym_old.cum_ret,smooth:true,symbol:'none',lineStyle:{color:'#8b949e',width:1.5,type:'dashed'}},
        {name:'纯WTS',  type:'line',data:full.pos_wts.cum_ret,smooth:true,symbol:'none',lineStyle:{color:'#3fb950',width:1.2}},
        {name:'BNH',    type:'line',data:full.pos_wts.bnh_ret,smooth:true,symbol:'none',lineStyle:{color:'#333',width:1.5,type:'dashed'}},
      ]
    },true);
  }

  ['P1','P2','P3'].forEach(p=>{
    const pr=ed.periods[p]; if(!pr||!pr.pos_asym_new)return;
    const el=$(`c-mini-${p.toLowerCase()}`); if(!el)return;
    const key=`mini-${p}-${n}`;
    if(!C[key])C[key]=echarts.init(el,'dark');
    C[key].setOption({
      backgroundColor:'transparent',
      grid:{top:4,bottom:16,left:32,right:6},
      xAxis:{type:'category',data:pr.pos_asym_new.dates,axisLine:{lineStyle:{color:'#30363d'}},
        axisLabel:{color:'#8b949e',fontSize:7,interval:'auto'}},
      yAxis:{scale:true,splitLine:{lineStyle:{color:'#21262d'}},
        axisLabel:{color:'#8b949e',fontSize:7,formatter:v=>v+'%'}},
      series:[
        {type:'line',data:pr.pos_asym_new.cum_ret,smooth:true,symbol:'none',lineStyle:{color:'#ffa657',width:2}},
        {type:'line',data:pr.pos_asym_c_new.cum_ret,smooth:true,symbol:'none',lineStyle:{color:'#58a6ff',width:1.2}},
        {type:'line',data:pr.pos_asym_old.cum_ret,smooth:true,symbol:'none',lineStyle:{color:'#8b949e',width:1,type:'dashed'}},
        {type:'line',data:pr.pos_asym_new.bnh_ret,smooth:true,symbol:'none',lineStyle:{color:'#333',width:1,type:'dashed'}},
      ]
    },true);
  });

  gc('c-alpha-bar').setOption({
    backgroundColor:'transparent',tooltip:{},
    legend:{bottom:0,textStyle:{color:'#8b949e',fontSize:8}},
    grid:{top:8,bottom:28,left:42,right:8},
    xAxis:{type:'category',data:PIDS.map(p=>PLABELS[p]),axisLabel:{color:'#8b949e',fontSize:8,interval:0}},
    yAxis:{splitLine:{lineStyle:{color:'#21262d'}},axisLabel:{color:'#8b949e',fontSize:8,formatter:v=>v+'%'}},
    series:STRATS.map(s=>({
      name:s.l,type:'bar',barMaxWidth:12,
      data:PIDS.map(p=>{const r=ed.periods[p]?.[s.k]; return r?r.metrics.alpha:null;}),
      itemStyle:{color:s.c},
    }))
  },true);

  gc('c-trades-bar').setOption({
    backgroundColor:'transparent',tooltip:{},
    legend:{bottom:0,textStyle:{color:'#8b949e',fontSize:8}},
    grid:{top:8,bottom:28,left:36,right:60},
    xAxis:{type:'category',data:STRATS.slice(0,3).map(s=>s.l),axisLabel:{color:'#8b949e',fontSize:9}},
    yAxis:[
      {name:'笔数',splitLine:{lineStyle:{color:'#21262d'}},axisLabel:{color:'#8b949e',fontSize:8}},
      {name:'持多%',max:100,axisLabel:{color:'#8b949e',fontSize:8,formatter:v=>v+'%'},splitLine:{show:false}}
    ],
    series:[
      {name:'交易笔数',type:'bar',barMaxWidth:28,yAxisIndex:0,
        data:STRATS.slice(0,3).map(s=>{const r=ed.periods['全程']?.[s.k];return r?r.metrics.n_trades:null;}),
        itemStyle:{color(p){return STRATS[p.dataIndex].c;}},
        label:{show:true,position:'top',color:'#8b949e',fontSize:10}},
      {name:'持多天%',type:'line',yAxisIndex:1,symbol:'circle',symbolSize:6,
        data:STRATS.slice(0,3).map(s=>{const r=ed.periods['全程']?.[s.k];return r?r.metrics.long_pct:null;}),
        lineStyle:{color:'#ffa657',width:2},itemStyle:{color:'#ffa657'}},
    ]
  },true);

  // summary table
  const cols = ['pos_asym_new','pos_asym_c_new','pos_asym_old'];
  const colColors = ['#ffa657','#58a6ff','#8b949e'];
  const colLabels = ['v2新参','v2确认','v1旧参'];
  let th=`<thead><tr><th class="nm">标的</th>`;
  PIDS.forEach(p=>{ th+=`<th colspan="${cols.length}" style="color:${PCOLS[p]}">${p}: α</th>`; });
  th+=`</tr><tr><th class="nm">参数变化</th>`;
  PIDS.forEach(()=>{
    cols.forEach((_,i)=>{ th+=`<th style="color:${colColors[i]}">${colLabels[i]}</th>`; });
  });
  th+=`</tr></thead>`;
  let tb=`<tbody>`;
  NS.forEach(nm=>{
    const ed2=D[nm];
    const pc2=ed2.params_changed;
    tb+=`<tr><td class="nm">${nm}<br><span class="sub">${pc2?`${ed2.old_params.same}/${ed2.old_params.rev} → <b style="color:#ffa657">${ed2.new_params.same}/${ed2.new_params.rev}</b>`:`${ed2.new_params.same}/${ed2.new_params.rev}(不变)`}</span></td>`;
    PIDS.forEach(p=>{
      const pr=ed2.periods[p];
      if(!pr){tb+=`<td colspan="${cols.length}" class="m">N/A</td>`;return;}
      const alphas=cols.map(k=>pr[k]?pr[k].metrics.alpha:null);
      const maxA=Math.max(...alphas.filter(a=>a!==null));
      alphas.forEach((a,si)=>{
        const isBest=a!==null&&Math.abs(a-maxA)<0.01;
        tb+=`<td class="${a!==null?cc(a):'m'} ${isBest?'winner':''}" style="${isBest?'background:'+colColors[si]+'15':''}">
          ${a!==null?p1(a):'--'}</td>`;
      });
    });
    tb+=`</tr>`;
    tb+=`<tr class="sub"><td class="nm sub">收益</td>`;
    PIDS.forEach(p=>{
      const pr=ed2.periods[p];
      if(!pr){tb+=`<td colspan="${cols.length}"></td>`;return;}
      cols.forEach(k=>{const r=pr[k];tb+=`<td class="sub ${r?cc(r.metrics.total_return):'m'}">${r?p1(r.metrics.total_return):'--'}</td>`;});
    });
    tb+=`</tr>`;
  });
  tb+=`</tbody>`;
  $('tbl').innerHTML=th+tb;
}

function sel(n){cur=n;renderSide();renderMain(n);}
sel(cur);
window.addEventListener('resize',()=>Object.values(C).forEach(c=>c.resize()));
</script>
</body>
</html>'''.replace('__DATA__', raw)

out = OUTPUT / 'asym_v2_comparison.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"HTML生成: {out}  ({out.stat().st_size//1024} KB)")
