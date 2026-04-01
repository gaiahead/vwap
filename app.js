function getVmsColor(s) {
  if (s <= 0)    return '#1e293b';
  if (s >= 0.03) return '#15803d';
  if (s >= 0.02) return '#4ade80';
  if (s >= 0.01) return '#94a3b8';
  return '#f87171';
}

const GRID='#1e2535', TICK='#475569';
const GROUP_ORDER = ['g1','g2','g3'];

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '10d';
let currentDetailName = null;
const detailCache = {};

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
  const allNames = Object.keys(data).filter(k=>k!=='_meta');
  const namesByGroup = {};
  GROUP_ORDER.forEach(g=>{ namesByGroup[g]=[]; });
  allNames.forEach(n=>{ const g=data[n].group; if(namesByGroup[g]) namesByGroup[g].push(n); });

  document.getElementById('updated').textContent =
    (data._meta?.updated_at||'')+' 기준';

  function get10d(name){ return data[name]?.vwap_structure?.[0]?.norm??null; }

  // ─── VMS 계산 ──────────────────────────────────────────
  const VMS_DECAY = 0.75;

  function calcVMS(name) {
    const vs = data[name]?.vwap_structure;
    if (!vs) return null;
    const vmap = {};
    vs.forEach(v => { vmap[v.window] = v.vwap; });
    if (!vmap[10] || !vmap[200]) return null;

    const weights = Array.from({length:10}, (_,i) => 10 * Math.pow(VMS_DECAY, i));
    const totalW = weights.reduce((a,b)=>a+b, 0);

    let weightedSum = 0;
    const rowScores = [];

    for (let i = 0; i < 10; i++) {
      const endpoint = (i+1)*10;
      const cellScores = [];
      for (let j = 1; j <= 10; j++) {
        const start = endpoint + j*10;
        if (!vmap[start]) continue;
        const cell = Math.max(Math.pow(vmap[endpoint] / vmap[start], 1/j) - 1, 0);
        cellScores.push(cell);
      }
      const rowScore = cellScores.length > 0 ? cellScores.reduce((a,b)=>a+b,0)/cellScores.length : 0;
      rowScores.push(rowScore);
      weightedSum += weights[i] * rowScore;
    }

    return { vms: weightedSum/totalW, rowScores };
  }

  function renderVMS() {
    const targets = ['삼성전자','SK하이닉스','한미반도체','리노공업'];
    const hasVMS = targets.some(n => data[n]);
    if (!hasVMS) return;

    document.getElementById('vms-section').style.display = '';
    const tbody = document.getElementById('vms-body');
    tbody.innerHTML = '';

    const rows = allNames
      .map(n => ({ name: n, result: calcVMS(n) }))
      .filter(r => r.result !== null)
      .sort((a,b) => b.result.vms - a.result.vms);

    rows.forEach(({name, result}) => {
      const {vms, rowScores} = result;
      const vmsColor = getVmsColor(vms);
      const tr = document.createElement('tr');
      const cells = [
        `<td>${name}</td>`,
        `<td style="color:${vmsColor};font-weight:700">${vms <= 0 ? '–' : (vms * 100).toFixed(1) + '%'}</td>`,
        ...rowScores.map(s => {
          return `<td style="color:${getVmsColor(s)}">${s <= 0 ? '–' : (s * 100).toFixed(1) + '%'}</td>`;
        })
      ];
      tr.innerHTML = cells.join('');
      tbody.appendChild(tr);
    });
  }

  // ─── Detail section ────────────────────────────────────
  const detailSection = document.getElementById('detail-section');
  const detailContent = document.getElementById('detail-content');
  const detailTitle = document.getElementById('detail-title');

  document.getElementById('detail-close').addEventListener('click', () => {
    detailSection.style.display = 'none';
    currentDetailName = null;
    location.hash = '';
    renderCards();
  });

  async function fetchDetail(ticker, name) {
    detailSection.style.display = '';
    currentDetailName = name;
    renderCards();

    if (detailCache[ticker]) {
      renderDetail(detailCache[ticker]);
      return;
    }

    detailContent.innerHTML = '<div class="loading">Loading...</div>';
    detailTitle.textContent = name;

    try {
      const resp = await fetch(`detail_data/${encodeURIComponent(ticker)}.json`);
      if (!resp.ok) throw new Error('not found');
      const json = await resp.json();
      detailCache[ticker] = json;
      // Restore panel HTML after loading spinner
      detailContent.innerHTML = buildPanelHTML();
      initVpTabs();
      renderDetail(json);
    } catch {
      detailContent.innerHTML = '<div class="loading">Data not available</div>';
    }
  }

  function buildPanelHTML() {
    const vpButtons = ['10d','20d','30d','40d','50d','60d','70d','80d','90d','100d',
      '110d','120d','130d','140d','150d','160d','170d','180d','190d','200d']
      .map(p => `<button class="vp-tab${p===currentVpPeriod?' active':''}" data-period="${p}">${p}</button>`)
      .join('');
    return `
      <div class="panel-box">
        <div class="panel-title">Price + VWAP Lines</div>
        <div style="position:relative;height:440px"><canvas id="chart-price"></canvas></div>
      </div>
      <div class="panel-box" style="margin-top:16px">
        <div class="panel-title">Volume Profile</div>
        <div class="vp-tabs" id="vp-tabs">${vpButtons}</div>
        <div style="position:relative;height:440px"><canvas id="chart-vp"></canvas></div>
      </div>
      <div class="panel-box" style="margin-top:16px">
        <div class="panel-title">VMS Matrix (VWAP Momentum Score)</div>
        <div id="vms-matrix"></div>
      </div>
    `;
  }

  function initVpTabs() {
    document.getElementById('vp-tabs').addEventListener('click', e => {
      if (!e.target.matches('.vp-tab')) return;
      currentVpPeriod = e.target.dataset.period;
      document.querySelectorAll('.vp-tab').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const ticker = data[currentDetailName]?.ticker;
      if (ticker && detailCache[ticker]) renderVpChart(detailCache[ticker], currentVpPeriod);
    });
  }

  // Initial VP tab handler (for static HTML case)
  initVpTabs();

  function renderDetail(detailData) {
    detailTitle.textContent = detailData.name;
    renderPriceChart(detailData);
    renderVpChart(detailData, currentVpPeriod);
    renderVMSMatrix(detailData);
    detailSection.scrollIntoView({behavior:'smooth', block:'start'});
  }

  // ─── Panel A: Price + VWAP ─────────────────────────────
  function renderPriceChart(detailData) {
    const ohlcv = detailData.ohlcv;
    const labels = ohlcv.map(d => d.date);
    const closes = ohlcv.map(d => d.close);
    const vwap10 = ohlcv.map(d => d.vwap_10d);

    const vp = detailData.volume_profile;
    const annotations = {};

    const v200 = vp['200d']?.vwap;
    if (v200 != null) {
      annotations['vwap_200d'] = {
        type: 'line', yMin: v200, yMax: v200,
        borderColor: '#94a3b8', borderWidth: 1.5, borderDash: [6, 3],
        label: {display: true, content: `VWAP 200d: ${v200.toLocaleString()}`, position: 'start',
          color: '#94a3b8', backgroundColor: 'rgba(15,17,23,0.85)', font: {size: 9, weight: 'bold'}, padding: {x: 4, y: 2}}
      };
    }

    const config = {
      type: 'line',
      data: {
        labels,
        datasets: [
          {label: 'Close', data: closes, borderColor: '#475569', borderWidth: 1, pointRadius: 0, tension: 0.1, fill: false, order: 2},
          {label: 'VWAP 10d', data: vwap10, borderColor: '#e2e8f0', borderWidth: 2, borderDash: [4, 2], pointRadius: 0, tension: 0.2, fill: false, order: 1}
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: {duration: 200},
        interaction: {mode: 'index', intersect: false},
        plugins: {
          legend: {display: true, labels: {color: '#94a3b8', font: {size: 10}, boxWidth: 12, padding: 10}},
          annotation: {annotations},
          tooltip: {callbacks: {label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y?.toLocaleString(undefined, {maximumFractionDigits: 2})}`}}
        },
        scales: {
          x: {ticks: {color: TICK, font: {size: 9}, maxTicksLimit: 12, maxRotation: 0}, grid: {color: GRID}},
          y: {ticks: {color: TICK, font: {size: 10}}, grid: {color: GRID}}
        }
      }
    };

    if (priceChart) priceChart.destroy();
    priceChart = new Chart(document.getElementById('chart-price'), config);
  }

  // ─── Panel B: Volume Profile ───────────────────────────
  function renderVpChart(detailData, period) {
    const vp = detailData.volume_profile[period];
    if (!vp) { if (vpChart) vpChart.destroy(); vpChart = null; return; }

    const buckets = vp.buckets;
    const labels = buckets.map(b => b.price.toLocaleString(undefined, {maximumFractionDigits: 2}));
    const volumes = buckets.map(b => b.volume);

    const annotations = {};
    const vwapIdx = buckets.findIndex(b => b.price >= vp.vwap);
    if (vwapIdx >= 0) {
      annotations.vwapLine = {
        type: 'line', scaleID: 'y', value: vwapIdx,
        borderColor: '#60a5fa', borderWidth: 2,
        label: {display: true, content: `VWAP ${vp.vwap.toLocaleString()}`, color: '#60a5fa',
          backgroundColor: 'rgba(15,17,23,0.85)', font: {size: 9}, position: 'end', padding: {x: 3, y: 1}}
      };
    }
    const cp = detailData.latest_price;
    const cpIdx = buckets.findIndex(b => b.price >= cp);
    if (cpIdx >= 0) {
      annotations.priceLine = {
        type: 'line', scaleID: 'y', value: cpIdx,
        borderColor: '#f8fafc', borderWidth: 1.5, borderDash: [4, 2],
        label: {display: true, content: `Price ${cp.toLocaleString()}`, color: '#f8fafc',
          backgroundColor: 'rgba(15,17,23,0.85)', font: {size: 9}, position: 'start', padding: {x: 3, y: 1}}
      };
    }

    const config = {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Volume', data: volumes,
          backgroundColor: volumes.map((_, i) => {
            const price = buckets[i].price;
            return price >= vp.vwap ? 'rgba(74,222,128,0.5)' : 'rgba(248,113,113,0.5)';
          }),
          borderColor: volumes.map((_, i) => {
            const price = buckets[i].price;
            return price >= vp.vwap ? '#4ade80' : '#f87171';
          }),
          borderWidth: 1
        }]
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: {duration: 200},
        plugins: {
          legend: {display: false},
          annotation: {annotations}
        },
        scales: {
          x: {ticks: {color: TICK, font: {size: 9}}, grid: {color: GRID}},
          y: {reverse: true, ticks: {color: TICK, font: {size: 8}}, grid: {color: GRID}}
        }
      }
    };

    if (vpChart) vpChart.destroy();
    vpChart = new Chart(document.getElementById('chart-vp'), config);
  }

  // ─── Panel C: VMS Matrix ──────────────────────────────
  function renderVMSMatrix(detailData) {
    const vms = detailData.vms_matrix;
    const container = document.getElementById('vms-matrix');
    container.innerHTML = '';

    const decay = 0.75;
    const weights = Array.from({length: 10}, (_, i) => 10 * Math.pow(decay, i));
    const maxW = Math.max(...weights);

    const cellMap = {};
    vms.cells.forEach(c => { cellMap[`${c.endpoint}_${c.start}`] = c; });

    const grid = document.createElement('div');
    grid.className = 'vms-grid';

    grid.innerHTML = `
      <div class="hdr"></div>
      <div class="hdr">EP</div>
      ${Array.from({length:10}, (_,j) => `<div class="hdr">+${(j+1)*10}d</div>`).join('')}
      <div class="hdr">Score</div>
    `;

    for (let i = 0; i < 10; i++) {
      const endpoint = (i + 1) * 10;
      const w = weights[i];
      const barWidth = Math.round(w / maxW * 36);

      const wCell = document.createElement('div');
      wCell.style.cssText = 'padding:4px 2px;display:flex;align-items:center;justify-content:center';
      wCell.innerHTML = `<div class="weight-bar" style="width:${barWidth}px"></div>`;
      grid.appendChild(wCell);

      const epCell = document.createElement('div');
      epCell.style.cssText = 'color:#94a3b8;font-weight:600;padding:6px 2px;text-align:center';
      epCell.textContent = `${endpoint}d`;
      grid.appendChild(epCell);

      for (let j = 1; j <= 10; j++) {
        const start = endpoint + j * 10;
        const key = `${endpoint}_${start}`;
        const cell = document.createElement('div');
        const d = cellMap[key];

        if (d) {
          const score = d.score != null ? d.score : 0;
          const cc = getVmsColor(score);
          cell.className = 'vms-cell';
          cell.style.backgroundColor = cc;
          cell.style.color = score >= 0.03 ? '#0f1117' : '#e2e8f0';
          cell.textContent = score <= 0 ? '–' : (score * 100).toFixed(1) + '%';
        } else {
          cell.className = 'vms-cell empty';
          cell.textContent = '·';
        }
        grid.appendChild(cell);
      }

      const rsCell = document.createElement('div');
      rsCell.className = 'row-score';
      const rs = vms.row_scores[i];
      rsCell.textContent = rs <= 0 ? '–' : (rs * 100).toFixed(1) + '%';
      rsCell.style.color = getVmsColor(rs);
      grid.appendChild(rsCell);
    }

    container.appendChild(grid);

    const summary = document.createElement('div');
    summary.className = 'vms-summary';
    const vmsColor = getVmsColor(vms.vms);
    const vmsDisplay = vms.vms <= 0 ? '–' : (vms.vms * 100).toFixed(1) + '%';
    const gaugePct = Math.min(vms.vms / 0.05 * 100, 100).toFixed(1);
    summary.innerHTML = `
      <span style="color:#94a3b8">VMS</span>
      <span class="vms-val" style="color:${vmsColor}">${vmsDisplay}</span>
      <div class="gauge-track">
        <div class="gauge-fill" style="width:${gaugePct}%;background:${vmsColor}"></div>
      </div>
      <span style="color:#475569;font-size:0.7rem">${vmsDisplay}</span>
    `;
    container.appendChild(summary);
  }

  // ─── Cards ─────────────────────────────────────────────
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
        const isActive = name === currentDetailName;
        const v10      = get10d(name);
        const btn = document.createElement('div');
        btn.className='asset-btn'+(isActive?' detail-active':'');
        btn.style.setProperty('--c',color);
        const vmsResult = calcVMS(name);
        const vmsStr = vmsResult ? `VMS ${vmsResult.vms <= 0 ? '–' : (vmsResult.vms * 100).toFixed(1) + '%'}` : '';
        btn.innerHTML=`
          <div class="indicator"></div>
          <div class="name">${name}</div>
          <div class="val" style="color:${color}">${v10!=null?v10.toFixed(2):'–'}</div>
          <div class="vms">${vmsStr}</div>
        `;
        btn.addEventListener('click',()=>{
          const ticker = data[name]?.ticker;
          if(!ticker) return;
          currentVpPeriod = '10d';
          location.hash = encodeURIComponent(ticker);
          fetchDetail(ticker, name);
        });
        div.appendChild(btn);
      });
      groupsEl.appendChild(div);
    });
  }

  renderCards();
  renderVMS();

  // ─── URL hash → auto open ──────────────────────────────
  function handleHash() {
    const hash = decodeURIComponent(location.hash.slice(1));
    if (!hash) return;
    const matched = allNames.find(n => data[n]?.ticker === hash);
    if (matched) fetchDetail(hash, matched);
  }
  handleHash();
});

// VMS 가중치 테이블
(function(){
  const decay = 0.75;
  const weights = Array.from({length:10}, (_,i) => +(10 * Math.pow(decay, i)).toFixed(4));
  const total = weights.reduce((a,b)=>a+b,0);
  const tbody = document.getElementById('vms-weight-table');
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
  const tfootr = document.createElement('tr');
  tfootr.innerHTML = `
    <td style="padding:6px 12px;color:#475569;border-top:1px solid #1e2535;font-weight:600">합계</td>
    <td style="padding:6px 12px;text-align:right;color:#475569;border-top:1px solid #1e2535">${total.toFixed(4)}</td>
    <td style="padding:6px 12px;text-align:right;color:#475569;border-top:1px solid #1e2535">100.00%</td>
    <td style="padding:6px 12px 6px 16px;color:#334155;border-top:1px solid #1e2535">10~50d: 80.8% / 60~100d: 19.2%</td>
  `;
  tbody.appendChild(tfootr);
})();
