const GRID='#1e2535', TICK='#475569';

const STRUCT_LABELS = ['200d','190d','180d','170d','160d','150d','140d','130d','120d','110d',
                       '100d','90d','80d','70d','60d','50d','40d','30d','20d','10d'];

const GROUP_ORDER = ['g1','g2','g3'];

let structChart;
let activeSet = new Set(['TLT']);

function rankColor(t){
  if(t>=0.5){
    const s=(t-0.5)*2;
    return `rgb(${Math.round(107+(34-107)*s)},${Math.round(114+(197-114)*s)},${Math.round(128+(94-128)*s)})`;
  } else {
    const s=t*2;
    return `rgb(${Math.round(239+(107-239)*s)},${Math.round(68+(114-68)*s)},${Math.round(68+(128-68)*s)})`;
  }
}

function calcColors(names, data){
  const vals = names.map(n=>data[n]?.vwap_structure?.[0]?.norm??0);
  const min=Math.min(...vals), max=Math.max(...vals), range=max-min||1;
  const colors={};
  names.forEach((n,i)=>{ colors[n]=rankColor((vals[i]-min)/range); });
  return colors;
}

fetch('trend_data.json').then(r=>r.json()).then(data=>{
  // 그룹별 순서 유지
  const allNames = Object.keys(data).filter(k=>k!=='_meta');
  const namesByGroup = {};
  GROUP_ORDER.forEach(g=>{ namesByGroup[g]=[]; });
  allNames.forEach(n=>{ const g=data[n].group; if(namesByGroup[g]) namesByGroup[g].push(n); });

  document.getElementById('updated').textContent =
    (data._meta?.updated_at||'')+' 기준';

  function get10d(name){ return data[name]?.vwap_structure?.[0]?.norm??null; }

  // ─── SCI 계산 ──────────────────────────────────────────
  const SCI_DECAY = 0.75;
  const SCI_THRESHOLD = 0.01;  // start × 1% (10d당, ≈ 연30% 기준)

  function calcSCI(name) {
    const vs = data[name]?.vwap_structure;
    if (!vs) return null;
    const vmap = {};
    vs.forEach(v => { vmap[v.window] = v.vwap; });
    if (!vmap[10] || !vmap[200]) return null;

    const weights = Array.from({length:10}, (_,i) => 10 * Math.pow(SCI_DECAY, i));
    const totalW = weights.reduce((a,b)=>a+b, 0);

    let weightedSum = 0;
    const rowScores = [];

    for (let i = 0; i < 10; i++) {
      const endpoint = (i+1)*10;
      let above = 0, total = 0;
      for (let j = 1; j <= 10; j++) {
        const start = endpoint + j*10;
        if (!vmap[start]) continue;
        const slope = (vmap[endpoint] - vmap[start]) / j;
        if (slope > vmap[start] * SCI_THRESHOLD) above++;
        total++;
      }
      const rowScore = total > 0 ? above/total : 0;
      rowScores.push(rowScore);
      weightedSum += weights[i] * rowScore;
    }

    return { sci: weightedSum/totalW, rowScores };
  }

  function renderSCI() {
    const targets = ['삼성전자','SK하이닉스','한미반도체','리노공업'];
    const hasSCI = targets.some(n => data[n]);
    if (!hasSCI) return;

    document.getElementById('sci-section').style.display = '';
    const tbody = document.getElementById('sci-body');
    tbody.innerHTML = '';

    // SCI 기준 정렬
    const rows = allNames
      .map(n => ({ name: n, result: calcSCI(n) }))
      .filter(r => r.result !== null)
      .sort((a,b) => b.result.sci - a.result.sci);

    rows.forEach(({name, result}) => {
      const {sci, rowScores} = result;
      const price = data[name]?.latest_price;
      const sciColor = sci >= 0.8 ? '#4ade80' : sci >= 0.6 ? '#94a3b8' : '#f87171';
      const tr = document.createElement('tr');
      const cells = [
        `<td>${name}</td>`,
        `<td style="color:${sciColor};font-weight:700">${sci.toFixed(3)}</td>`,

        ...rowScores.map(s => {
          const c = s >= 0.8 ? '#4ade80' : s >= 0.5 ? '#94a3b8' : '#475569';
          return `<td style="color:${c}">${(s*10).toFixed(0)}/10</td>`;
        })
      ];
      tr.innerHTML = cells.join('');
      tbody.appendChild(tr);
    });
  }

  const groupsEl = document.getElementById('groups');

  function renderCards(){
    const colors = calcColors(allNames, data);
    groupsEl.innerHTML='';
    GROUP_ORDER.forEach(g=>{
      const names = namesByGroup[g];
      if(!names?.length) return;
      const div = document.createElement('div');
      div.className='group';
      names.forEach(name=>{
        const color    = colors[name];
        const isActive = activeSet.has(name);
        const v10      = get10d(name);
        const btn = document.createElement('div');
        btn.className='asset-btn'+(isActive?' active':'');
        btn.style.setProperty('--c',color);
        const sciResult = calcSCI(name);
        const sciStr = sciResult ? `SCI ${sciResult.sci.toFixed(3)}` : '';
        btn.innerHTML=`
          <div class="indicator"></div>
          <div class="name">${name}</div>
          <div class="val" style="color:${color}">${v10!=null?v10.toFixed(2):'–'}</div>
          <div class="sci">${sciStr}</div>
        `;
        btn.addEventListener('click',()=>{
          const ticker = data[name]?.ticker;
          if(ticker) location.href = `detail.html?ticker=${encodeURIComponent(ticker)}`;
        });
        btn.addEventListener('dblclick',(e)=>{
          e.preventDefault();
          if(activeSet.has(name)) activeSet.delete(name);
          else activeSet.add(name);
          renderCards();
          updateChart();
        });
        div.appendChild(btn);
      });
      groupsEl.appendChild(div);
    });
  }

  function makeDatasets(){
    const colors = calcColors(allNames, data);
    return allNames.map(name=>{
      const isActive = activeSet.has(name);
      const reversed = [...(data[name].vwap_structure||[])].reverse();
      const color    = colors[name];
      return {
        label: name,
        data:  reversed.map(s=>s.norm),
        rawVwap: reversed.map(s=>s.vwap),
        borderColor: color,
        borderWidth: isActive?2:0,
        pointRadius: isActive?3:0,
        pointHoverRadius: isActive?4:0,
        pointBackgroundColor: color,
        tension: 0.3,
        fill: false,
        hidden: !isActive,
      };
    });
  }

  function makeAnnotations(){
    const colors = calcColors(allNames, data);
    const annotations = {
      base:{type:'line',yMin:100,yMax:100,borderColor:'#475569',borderWidth:1.5},
    };
    const active = allNames.filter(n=>activeSet.has(n))
      .map(n=>({name:n, val:get10d(n)}))
      .filter(d=>d.val!=null)
      .sort((a,b)=>b.val-a.val);

    active.forEach(({name,val})=>{
      annotations['lbl_'+name]={
        type:'label', xValue:19, yValue:val,
        content: name+' '+val.toFixed(2),
        color: colors[name],
        font:{size:10,weight:'bold'},
        backgroundColor:'rgba(15,17,23,0.85)',
        padding:{x:4,y:2},
        position:{x:'start',y:'center'},
        xAdjust:4,
      };
    });
    return annotations;
  }

  function updateChart(){
    structChart.data.datasets = makeDatasets();
    structChart.options.plugins.annotation.annotations = makeAnnotations();
    structChart.update('none');
  }

  renderCards();
  renderSCI();

  structChart = new Chart(document.getElementById('chart-structure'),{
    type:'line',
    data:{labels:STRUCT_LABELS, datasets:makeDatasets()},
    options:{
      responsive:true,
      maintainAspectRatio:false,
      animation:{duration:300},
      interaction:{mode:'index',intersect:false},
      layout:{padding:0},
      plugins:{
        legend:{display:false},
        annotation:{annotations:makeAnnotations()},
        tooltip:{callbacks:{label:ctx=>{
          const norm = ctx.parsed.y?.toFixed(2);
          const raw = ctx.dataset.rawVwap?.[ctx.dataIndex];
          const rawStr = raw != null ? raw.toLocaleString(undefined,{maximumFractionDigits:2}) : '–';
          return ` ${ctx.dataset.label}: ${norm} (VWAP ${rawStr})`;
        }}}
      },
      scales:{
        x:{ticks:{color:TICK,font:{size:10}},grid:{color:GRID}},
        y:{
          ticks:{color:TICK,font:{size:10},count:11,callback:v=>v.toFixed(2)},
          grid:{color:GRID},
          afterDataLimits(scale){
            if(activeSet.size===0){scale.min=100;scale.max=200;}
          }
        },
      }
    }
  });

  // 리사이즈 시 차트 높이 반응형
  function resizeChart(){
    const wrap = document.querySelector('.chart-wrap');
    const h = Math.max(300, Math.min(420, window.innerHeight * 0.45));
    wrap.style.height = h + 'px';
    structChart.resize();
  }
  resizeChart();
  window.addEventListener('resize', resizeChart);
});

// SCI 가중치 테이블
(function(){
  const decay = 0.75;
  const weights = Array.from({length:10}, (_,i) => +(10 * Math.pow(decay, i)).toFixed(4));
  const total = weights.reduce((a,b)=>a+b,0);
  const tbody = document.getElementById('sci-weight-table');
  weights.forEach((w, i) => {
    const ep = (i+1)*10;
    const pct = (w/total*100).toFixed(2);
    const barW = Math.round(w/total*120);
    const bar = `<span style="display:inline-block;width:${barW}px;height:8px;background:#1e3a5f;border-radius:2px;vertical-align:middle;margin-right:6px"></span>`;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="padding:4px 12px;color:#94a3b8">${ep}d</td>
      <td style="padding:4px 12px;text-align:right;color:#cbd5e1">${w.toFixed(4)}</td>
      <td style="padding:4px 12px;text-align:right;color:#60a5fa">${pct}%</td>
      <td style="padding:4px 12px 4px 16px;color:#334155">${bar}${ep+10}d ~ ${ep+100}d</td>
    `;
    tbody.appendChild(tr);
  });
  // 합계 행
  const tfootr = document.createElement('tr');
  tfootr.innerHTML = `
    <td style="padding:6px 12px;color:#475569;border-top:1px solid #1e2535;font-weight:600">합계</td>
    <td style="padding:6px 12px;text-align:right;color:#475569;border-top:1px solid #1e2535">${total.toFixed(4)}</td>
    <td style="padding:6px 12px;text-align:right;color:#475569;border-top:1px solid #1e2535">100.00%</td>
    <td style="padding:6px 12px 6px 16px;color:#334155;border-top:1px solid #1e2535">10~50d: 80.8% / 60~100d: 19.2%</td>
  `;
  tbody.appendChild(tfootr);
})();
