function getMomentumColor(s) {
  if (s >= 0.03)  return '#16a34a';   // 3%+ → 녹 (밝은 테마용)
  if (s >= 0.01)  return '#475569';   // 1%+ → 회
  if (s >= 0)     return '#64748b';   // 0%+ → 어두운 회
  if (s >= -0.01) return '#ea580c';   // -1%~0 → 주황
  return '#dc2626';                   // -1% 미만 → 적
}

const GRID='#e2e8f0', TICK='#64748b';
const GROUP_ORDER = ['g1','g2','g3','g4','g5'];

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '10d';
let currentDetailName = null;
const detailCache = {};
const DATA_VERSION = 'top-200d-20260517-2';

fetch(`trend_data.json?v=${DATA_VERSION}`, { cache: 'no-store' }).then(r=>r.json()).then(data=>{
  const allNames = Object.keys(data).filter(k => k !== '_meta');

  document.getElementById('updated').textContent =
    (data._meta?.updated_at || '') + ' 기준';

  // ─── VWAP Momentum 계산 ──────────────────────────────────────────
  const MOMENTUM_DECAY = 0.75;

  function calcVwapMomentum(name) {
    const vs = data[name]?.vwap_structure;
    if (!vs) return null;
    const vmap = {};
    vs.forEach(v => { vmap[v.window] = v.vwap; });
    if (!vmap[10] || !vmap[200]) return null;

    const weights = Array.from({length:10}, (_,i) => 10 * Math.pow(MOMENTUM_DECAY, i));
    const totalW = weights.reduce((a,b)=>a+b, 0);

    let weightedSum = 0;
    const rowScores = [];

    for (let i = 0; i < 10; i++) {
      const endpoint = (i+1)*10;
      let cellWeightedSum = 0, cellTotalW = 0;
      for (let j = 1; j <= 10; j++) {
        const start = endpoint + j*10;
        if (!vmap[start]) continue;
        const cell = Math.pow(vmap[endpoint] / vmap[start], 1/j) - 1;
        const cw = 10 * Math.pow(MOMENTUM_DECAY, j-1);  // +10d 가중 높음
        cellWeightedSum += cw * cell;
        cellTotalW += cw;
      }
      const rowScore = cellTotalW > 0 ? cellWeightedSum / cellTotalW : 0;
      rowScores.push(rowScore);
      weightedSum += weights[i] * rowScore;
    }

    return { momentum: weightedSum/totalW, rowScores };
  }


  function fmtPct(v) { return v == null ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`; }
  function fmtRate(v) { return v == null ? '–' : `${Number(v).toFixed(2)}%`; }
  function fmtDays(v) { return v == null ? '–' : Number(v).toFixed(1).replace(/\.0$/, ''); }
  function fmtStrategyVsHold(strategyVal, holdVal) {
    return `전략 ${fmtPct(strategyVal)} / 보유 ${fmtPct(holdVal)}`;
  }
  function dualStatColor(strategyVal, holdVal, isMdd=false) {
    const value = strategyVal ?? holdVal;
    if (value == null) return '#64748b';
    if (isMdd) return value <= -20 ? '#dc2626' : '#16a34a';
    return value >= 0 ? '#16a34a' : '#dc2626';
  }
  function getStrategyStateClass(strategy) {
    const latest = strategy?.latest;
    if (!latest) return 'neutral';
    return latest.action === '매수' ? 'buy' : 'sell';
  }
  function getSignalText(strategy) {
    const latest = strategy?.latest;
    if (!latest) return '–';
    return latest.action === '매수' ? 'BUY' : 'SELL';
  }
  function signalColor(type) {
    if (type === 'BUY') return '#16a34a';
    if (type === 'SELL') return '#dc2626';
    return '#64748b';
  }

  function renderMomentum() {
    const targets = ['삼성전자','SK하이닉스','한미반도체','리노공업'];
    const hasMomentumTargets = targets.some(n => data[n]);
    if (!hasMomentumTargets) return;

    document.getElementById('momentum-section').style.display = '';
    const tbody = document.getElementById('momentum-body');
    tbody.innerHTML = '';

    const rows = allNames
      .map(n => ({ name: n, result: calcVwapMomentum(n), strategy: data[n]?.strategy_signal }))
      .filter(r => r.result !== null)
      .sort((a,b) => b.result.momentum - a.result.momentum);

    rows.forEach(({name, result, strategy}) => {
      const {momentum} = result;
      const ticker = data[name]?.ticker;
      const latest = strategy?.latest || {};
      const momentumColor = getMomentumColor(momentum);
      const stateClass = getStrategyStateClass(strategy);
      const signalText = getSignalText(strategy);
      const rolling200 = strategy?.backtest?.rolling_200d || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.style.setProperty('--c', momentumColor);
      const cells = [
        `<td><span class="row-indicator"></span>${name}</td>`,
        `<td style="color:${momentumColor};font-weight:800">${(momentum * 100).toFixed(2)}</td>`,
        `<td style="color:${signalColor(signalText)};font-weight:800"><span class="strategy-badge ${stateClass}">${signalText}</span></td>`,
        `<td style="color:${(latest.vwap_5_20_momentum_pct ?? 0) >= 0 ? '#16a34a' : '#dc2626'};font-weight:800">${fmtPct(latest.vwap_5_20_momentum_pct)}</td>`,
        `<td>${latest.holding_days ?? '–'}</td>`,
        `<td style="color:${(latest.current_trade_return_pct ?? 0) >= 0 ? '#16a34a' : '#dc2626'};font-weight:800">${fmtPct(latest.current_trade_return_pct)}</td>`,
        `<td class="dual-stat" style="color:${dualStatColor(rolling200.strategy_return_pct, rolling200.buy_hold_return_pct)}">${fmtStrategyVsHold(rolling200.strategy_return_pct, rolling200.buy_hold_return_pct)}</td>`,
        `<td class="dual-stat" style="color:${dualStatColor(rolling200.strategy_mdd_pct, rolling200.buy_hold_mdd_pct, true)}">${fmtStrategyVsHold(rolling200.strategy_mdd_pct, rolling200.buy_hold_mdd_pct)}</td>`,
        `<td>${latest.last_signal || '–'} ${latest.last_signal_date ? latest.last_signal_date.slice(5) : ''}</td>`
      ];
      tr.innerHTML = cells.join('');
      tr.addEventListener('click', () => {
        if (!ticker) return;
        currentVpPeriod = '10d';
        location.hash = encodeURIComponent(ticker);
        fetchDetail(ticker, name);
      });
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
    renderMomentum();
  });

  async function fetchDetail(ticker, name) {
    detailSection.style.display = '';
    currentDetailName = name;
    renderMomentum();

    if (detailCache[ticker]) {
      renderDetail(detailCache[ticker]);
      return;
    }

    detailContent.innerHTML = '<div class="loading">Loading...</div>';
    detailTitle.textContent = name;

    try {
      const resp = await fetch(`detail_data/${encodeURIComponent(ticker)}.json?v=${DATA_VERSION}`, { cache: 'no-store' });
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
      <div class="panel-box strategy-panel">
        <div class="panel-title">Strategy Signal · VWAP 5/20</div>
        <div id="strategy-card"></div>
      </div>
      <div class="panel-box" style="margin-top:16px">
        <div class="panel-title">VWAP Lines · 5/20</div>
        <div style="position:relative;height:440px"><canvas id="chart-price"></canvas></div>
      </div>
      <div class="panel-box" style="margin-top:16px">
        <div class="panel-title">Volume Profile</div>
        <div class="vp-tabs" id="vp-tabs">${vpButtons}</div>
        <div style="position:relative;height:440px"><canvas id="chart-vp"></canvas></div>
      </div>
      <div class="panel-box" style="margin-top:16px">
        <div class="panel-title">VWAP Momentum Matrix</div>
        <div id="momentum-matrix"></div>
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
    renderStrategyCard(detailData);
    renderPriceChart(detailData);
    renderVpChart(detailData, currentVpPeriod);
    renderMomentumMatrix(detailData);
    detailSection.scrollIntoView({behavior:'smooth', block:'start'});
  }


  function renderStrategyCard(detailData) {
    const container = document.getElementById('strategy-card');
    if (!container) return;
    const strategy = detailData.strategy_signal;
    if (!strategy?.available) {
      container.innerHTML = '<div class="strategy-muted">전략 계산 데이터가 부족합니다.</div>';
      return;
    }
    const latest = strategy.latest;
    const bt = strategy.backtest || {};
    const cls = getStrategyStateClass(strategy);
    container.innerHTML = `
      <div class="strategy-grid">
        <div class="strategy-main ${cls}">
          <div class="strategy-label">현재 행동</div>
          <div class="strategy-action">${latest.action}</div>
          <div class="strategy-rule">매수 5&gt;20 · 매도 5&lt;20</div>
        </div>
        <div><div class="strategy-label">5/20 배열</div><div class="strategy-value">${latest.alignment}</div></div>
        <div><div class="strategy-label">5/20 모멘텀</div><div class="strategy-value ${latest.vwap_5_20_momentum_pct >= 0 ? 'pos' : 'neg'}">${fmtPct(latest.vwap_5_20_momentum_pct)}</div></div>
        <div><div class="strategy-label">보유일</div><div class="strategy-value">${latest.holding_days ?? '–'}</div></div>
        <div><div class="strategy-label">현재 거래 수익률</div><div class="strategy-value ${latest.current_trade_return_pct >= 0 ? 'pos' : 'neg'}">${fmtPct(latest.current_trade_return_pct)}</div></div>
        <div><div class="strategy-label">최근 신호</div><div class="strategy-value">${latest.last_signal || '–'} ${latest.last_signal_date || ''}</div></div>
        <div><div class="strategy-label">백테스트</div><div class="strategy-value">전략 ${fmtPct(bt.strategy_return_pct)} / 보유 ${fmtPct(bt.buy_hold_return_pct)}</div></div>
        <div><div class="strategy-label">MDD · 승률</div><div class="strategy-value">${fmtPct(bt.max_drawdown_pct)} · ${fmtRate(bt.win_rate_pct)}</div></div>
        <div><div class="strategy-label">노출 · 평균보유</div><div class="strategy-value">${fmtRate(bt.exposure_pct)} · ${fmtDays(bt.avg_holding_days)}일</div></div>
      </div>
    `;
  }

  // ─── Panel A: Price + VWAP ─────────────────────────────
  function renderPriceChart(detailData) {
    const ohlcv = detailData.ohlcv;
    const labels = ohlcv.map(d => d.date);
    const closes = ohlcv.map(d => d.close);
    const vwap5 = ohlcv.map(d => d.vwap_5d);
    const vwap20 = ohlcv.map(d => d.vwap_20d);
    const signalMap = new Map((detailData.strategy_signal?.signals || []).map(sig => [sig.date, sig]));
    const buyPoints = labels.map((date, i) => signalMap.get(date)?.type === 'BUY' ? closes[i] : null);
    const sellPoints = labels.map((date, i) => signalMap.get(date)?.type === 'SELL' ? closes[i] : null);

    const vp = detailData.volume_profile;
    const annotations = {};

    const v200 = vp['200d']?.vwap;
    if (v200 != null) {
      annotations['vwap_200d'] = {
        type: 'line', yMin: v200, yMax: v200,
        borderColor: '#64748b', borderWidth: 1.5, borderDash: [6, 3],
        label: {display: true, content: `VWAP 200d: ${v200.toLocaleString()}`, position: 'start',
          color: '#334155', backgroundColor: 'rgba(255,255,255,0.9)', font: {size: 9, weight: 'bold'}, padding: {x: 4, y: 2}}
      };
    }

    const config = {
      type: 'line',
      data: {
        labels,
        datasets: [
          {label: 'Close', data: closes, borderColor: '#64748b', borderWidth: 1, pointRadius: 0, tension: 0.1, fill: false, order: 5},
          {label: 'VWAP 5d', data: vwap5, borderColor: '#2563eb', borderWidth: 2.2, borderDash: [4, 2], pointRadius: 0, tension: 0.2, fill: false, order: 4},
          {label: 'VWAP 20d · Sell line', data: vwap20, borderColor: '#ea580c', borderWidth: 2.2, borderDash: [6, 3], pointRadius: 0, tension: 0.2, fill: false, order: 3},
          {label: 'BUY', data: buyPoints, type: 'line', showLine: false, pointStyle: 'triangle', pointRadius: 6, pointBackgroundColor: '#16a34a', pointBorderColor: '#166534', order: 1},
          {label: 'SELL', data: sellPoints, type: 'line', showLine: false, pointStyle: 'rectRot', pointRadius: 6, pointBackgroundColor: '#dc2626', pointBorderColor: '#991b1b', order: 1}
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: {duration: 200},
        interaction: {mode: 'index', intersect: false},
        plugins: {
          legend: {display: true, labels: {color: '#334155', font: {size: 10}, boxWidth: 12, padding: 10}},
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
        borderColor: '#2563eb', borderWidth: 2,
        label: {display: true, content: `VWAP ${vp.vwap.toLocaleString()}`, color: '#1d4ed8',
          backgroundColor: 'rgba(255,255,255,0.9)', font: {size: 9}, position: 'end', padding: {x: 3, y: 1}}
      };
    }
    // 현재가 라인 제거

    const config = {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Volume', data: volumes,
          backgroundColor: volumes.map((_, i) => {
            const price = buckets[i].price;
            return price >= vp.vwap ? 'rgba(34,197,94,0.35)' : 'rgba(239,68,68,0.32)';
          }),
          borderColor: volumes.map((_, i) => {
            const price = buckets[i].price;
            return price >= vp.vwap ? '#16a34a' : '#dc2626';
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

  // ─── Panel C: VWAP Momentum Matrix ──────────────────────────────
  function renderMomentumMatrix(detailData) {
    const momentumMatrix = detailData.vwap_momentum_matrix;
    const container = document.getElementById('momentum-matrix');
    container.innerHTML = '';

    const decay = 0.75;
    const weights = Array.from({length: 10}, (_, i) => 10 * Math.pow(decay, i));
    const maxW = Math.max(...weights);

    const cellMap = {};
    momentumMatrix.cells.forEach(c => { cellMap[`${c.endpoint}_${c.start}`] = c; });

    const wrap = document.createElement('div');
    wrap.className = 'momentum-grid-wrap';
    const grid = document.createElement('div');
    grid.className = 'momentum-grid';

    grid.innerHTML = `
      <div class="hdr"></div>
      <div class="hdr">EP</div>
      <div class="hdr">Momentum</div>
      ${Array.from({length:10}, (_,j) => `<div class="hdr">+${(j+1)*10}d</div>`).join('')}
    `;

    for (let i = 0; i < 10; i++) {
      const endpoint = (i + 1) * 10;
      const w = weights[i];
      const barWidth = Math.round(w / maxW * 36);

      const wCell = document.createElement('div');
      wCell.style.cssText = 'padding:4px 2px;display:flex;align-items:center;justify-content:center';
      wCell.innerHTML = '';  // 가중치 바 제거
      grid.appendChild(wCell);

      const epCell = document.createElement('div');
      epCell.style.cssText = 'color:#475569;font-weight:600;padding:6px 2px;text-align:center';
      epCell.textContent = `${endpoint}d`;
      grid.appendChild(epCell);

      const rsCell = document.createElement('div');
      rsCell.className = 'row-score';
      const rs = momentumMatrix.row_scores[i];
      rsCell.textContent = (rs * 100).toFixed(2);
      rsCell.style.color = getMomentumColor(rs);
      grid.appendChild(rsCell);

      for (let j = 1; j <= 10; j++) {
        const start = endpoint + j * 10;
        const key = `${endpoint}_${start}`;
        const cell = document.createElement('div');
        const d = cellMap[key];

        if (d) {
          const score = d.score != null ? d.score : 0;
          cell.className = 'momentum-cell';
          cell.style.backgroundColor = '#f8fafc';
          cell.style.color = getMomentumColor(score);
          cell.textContent = (score * 100).toFixed(2);
        } else {
          cell.className = 'momentum-cell empty';
          cell.textContent = '·';
        }
        grid.appendChild(cell);
      }

    }

    wrap.appendChild(grid);
    container.appendChild(wrap);

    // summary 제거
  }

  // ─── Legacy card renderer removed ───────────────────────
  function renderCards(){ renderMomentum(); }

  renderMomentum();

  // ─── URL hash → auto open ──────────────────────────────
  function handleHash() {
    const hash = decodeURIComponent(location.hash.slice(1));
    if (!hash) return;
    const matched = allNames.find(n => data[n]?.ticker === hash);
    if (matched) fetchDetail(hash, matched);
  }
  handleHash();
});

// VWAP Momentum 가중치 테이블
(function(){
  const decay = 0.75;
  const weights = Array.from({length:10}, (_,i) => +(10 * Math.pow(decay, i)).toFixed(4));
  const total = weights.reduce((a,b)=>a+b,0);
  const tbody = document.getElementById('momentum-weight-table');
  weights.forEach((w, i) => {
    const ep = (i+1)*10;
    const pct = (w/total*100).toFixed(2);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="padding:4px 12px;color:#475569">${ep}d</td>
      <td style="padding:4px 12px;text-align:right;color:#334155">${w.toFixed(4)}</td>
      <td style="padding:4px 12px;text-align:right;color:#2563eb">${pct}%</td>
      <td style="padding:4px 12px 4px 16px;color:#64748b">${ep+10}d ~ ${ep+100}d</td>
    `;
    tbody.appendChild(tr);
  });
  const tfootr = document.createElement('tr');
  tfootr.innerHTML = `
    <td style="padding:6px 12px;color:#475569;border-top:1px solid #e2e8f0;font-weight:600">합계</td>
    <td style="padding:6px 12px;text-align:right;color:#475569;border-top:1px solid #e2e8f0">${total.toFixed(4)}</td>
    <td style="padding:6px 12px;text-align:right;color:#475569;border-top:1px solid #e2e8f0">100.00%</td>
    <td style="padding:6px 12px 6px 16px;color:#64748b;border-top:1px solid #e2e8f0">10~50d: 80.8% / 60~100d: 19.2%</td>
  `;
  tbody.appendChild(tfootr);
})();
