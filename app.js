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
let currentVpPeriod = '20d';
let currentDetailName = null;
const detailCache = {};
const DATA_VERSION = 'recent-200-sortable-table-20260517';

fetch(`trend_data.json?v=${DATA_VERSION}`, { cache: 'no-store' }).then(r=>r.json()).then(data=>{
  const allNames = Object.keys(data).filter(k => k !== '_meta');

  document.getElementById('updated').textContent =
    (data._meta?.updated_at || '') + ' 기준';

  // ─── Formatting helpers ──────────────────────────────────────────
  function fmtPct(v) { return v == null ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`; }
  function fmtRate(v) { return v == null ? '–' : `${Number(v).toFixed(2)}%`; }
  function fmtDays(v) { return v == null ? '–' : Number(v).toFixed(1).replace(/\.0$/, ''); }
  function statColor(value, isMdd=false) {
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

  const sortFields = {
    name: r => r.name,
    last_signal_date: r => r.strategy.latest?.last_signal_date || '',
    vwap_5_20_return_pct: r => r.strategy.latest?.vwap_5_20_return_pct,
    vwap_5_200_return_pct: r => r.strategy.latest?.vwap_5_200_return_pct,
    holding_days: r => r.strategy.latest?.holding_days,
    current_trade_return_pct: r => r.strategy.latest?.current_trade_return_pct,
    strategy_return_pct: r => r.strategy.backtest?.rolling_200d?.strategy_return_pct,
    buy_hold_return_pct: r => r.strategy.backtest?.rolling_200d?.buy_hold_return_pct,
    strategy_mdd_pct: r => r.strategy.backtest?.rolling_200d?.strategy_mdd_pct,
    buy_hold_mdd_pct: r => r.strategy.backtest?.rolling_200d?.buy_hold_mdd_pct
  };
  const numericSortFields = new Set([
    'vwap_5_20_return_pct', 'vwap_5_200_return_pct', 'holding_days',
    'current_trade_return_pct', 'strategy_return_pct', 'buy_hold_return_pct',
    'strategy_mdd_pct', 'buy_hold_mdd_pct'
  ]);
  let sortState = { key: 'current_trade_return_pct', dir: 'desc' };

  function compareRows(a, b) {
    const getter = sortFields[sortState.key] || sortFields.current_trade_return_pct;
    const av = getter(a);
    const bv = getter(b);
    const dir = sortState.dir === 'asc' ? 1 : -1;
    if (numericSortFields.has(sortState.key)) {
      const an = av == null || Number.isNaN(Number(av)) ? -Infinity : Number(av);
      const bn = bv == null || Number.isNaN(Number(bv)) ? -Infinity : Number(bv);
      if (an !== bn) return (an - bn) * dir;
    } else {
      const cmp = String(av ?? '').localeCompare(String(bv ?? ''), 'ko-KR', { numeric: true });
      if (cmp !== 0) return cmp * dir;
    }
    return a.name.localeCompare(b.name, 'ko-KR');
  }

  function updateSortHeaders() {
    document.querySelectorAll('.momentum-table th[data-sort]').forEach(th => {
      const active = th.dataset.sort === sortState.key;
      th.classList.toggle('sort-active', active);
      th.dataset.sortDir = active ? sortState.dir : '';
      th.setAttribute('aria-sort', active ? (sortState.dir === 'asc' ? 'ascending' : 'descending') : 'none');
    });
  }

  document.querySelectorAll('.momentum-table th[data-sort]').forEach(th => {
    th.tabIndex = 0;
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      sortState = sortState.key === key
        ? { key, dir: sortState.dir === 'desc' ? 'asc' : 'desc' }
        : { key, dir: numericSortFields.has(key) ? 'desc' : 'asc' };
      renderMomentum();
    });
    th.addEventListener('keydown', e => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      th.click();
    });
  });

  function renderMomentum() {
    const targets = ['삼성전자','SK하이닉스','한미반도체','리노공업'];
    const hasMomentumTargets = targets.some(n => data[n]);
    if (!hasMomentumTargets) return;

    document.getElementById('momentum-section').style.display = '';
    const tbody = document.getElementById('momentum-body');
    tbody.innerHTML = '';

    const rows = allNames
      .map(n => ({ name: n, strategy: data[n]?.strategy_signal }))
      .filter(r => r.strategy?.available)
      .sort(compareRows);
    updateSortHeaders();

    rows.forEach(({name, strategy}) => {
      const ticker = data[name]?.ticker;
      const latest = strategy?.latest || {};
      const trendColor = statColor(latest.vwap_5_200_return_pct);
      const stateClass = getStrategyStateClass(strategy);
      const signalText = getSignalText(strategy);
      const rolling200 = strategy?.backtest?.rolling_200d || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.style.setProperty('--c', trendColor);
      const cells = [
        `<td><span class="row-indicator"></span>${name}</td>`,
        `<td class="recent-signal" style="color:${signalColor(latest.last_signal || signalText)};font-weight:800">${latest.last_signal || '–'} ${latest.last_signal_date ? latest.last_signal_date.slice(5) : ''}</td>`,
        `<td style="color:${statColor(latest.vwap_5_20_return_pct)};font-weight:800">${fmtPct(latest.vwap_5_20_return_pct)}</td>`,
        `<td style="color:${statColor(latest.vwap_5_200_return_pct)};font-weight:800">${fmtPct(latest.vwap_5_200_return_pct)}</td>`,
        `<td>${latest.holding_days ?? '–'}</td>`,
        `<td style="color:${statColor(latest.current_trade_return_pct)};font-weight:800">${fmtPct(latest.current_trade_return_pct)}</td>`,
        `<td style="color:${statColor(rolling200.strategy_return_pct)};font-weight:800">${fmtPct(rolling200.strategy_return_pct)}</td>`,
        `<td style="color:${statColor(rolling200.buy_hold_return_pct)};font-weight:800">${fmtPct(rolling200.buy_hold_return_pct)}</td>`,
        `<td style="color:${statColor(rolling200.strategy_mdd_pct, true)};font-weight:800">${fmtPct(rolling200.strategy_mdd_pct)}</td>`,
        `<td style="color:${statColor(rolling200.buy_hold_mdd_pct, true)};font-weight:800">${fmtPct(rolling200.buy_hold_mdd_pct)}</td>`
      ];
      tr.innerHTML = cells.join('');
      tr.addEventListener('click', () => {
        if (!ticker) return;
        currentVpPeriod = '20d';
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
    const vpButtons = ['5d','20d','200d']
      .map(p => `<button class="vp-tab${p===currentVpPeriod?' active':''}" data-period="${p}">${p}</button>`)
      .join('');
    return `
      <div class="panel-box">
        <div class="panel-title">VWAP Lines · 5/20/200</div>
        <div style="position:relative;height:440px"><canvas id="chart-price"></canvas></div>
      </div>
      <div class="panel-box" style="margin-top:16px">
        <div class="panel-title">Volume Profile</div>
        <div class="vp-tabs" id="vp-tabs">${vpButtons}</div>
        <div style="position:relative;height:440px"><canvas id="chart-vp"></canvas></div>
      </div>
    `;
  }

  function initVpTabs() {
    const tabs = document.getElementById('vp-tabs');
    if (!tabs) return;
    tabs.addEventListener('click', e => {
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
    detailSection.scrollIntoView({behavior:'smooth', block:'start'});
  }


  // ─── Panel A: Price + VWAP ─────────────────────────────
  function renderPriceChart(detailData) {
    const ohlcv = detailData.ohlcv;
    const labels = ohlcv.map(d => d.date);
    const closes = ohlcv.map(d => d.close);
    const vwap5 = ohlcv.map(d => d.vwap_5d);
    const vwap20 = ohlcv.map(d => d.vwap_20d);
    const signalMap = new Map((detailData.strategy_signal?.signals || []).map(sig => [sig.date, sig]));
    const buyPoints = labels.map((date, i) => signalMap.get(date)?.type === 'BUY' ? vwap5[i] : null);
    const sellPoints = labels.map((date, i) => signalMap.get(date)?.type === 'SELL' ? vwap5[i] : null);

    const vp = detailData.volume_profile;
    const vwap200 = vp?.['200d']?.vwap ?? null;
    const vwap200Line = labels.map(() => vwap200);
    const legendOrder = ['BUY', 'SELL', 'VWAP 5', 'VWAP 20', 'VWAP 200', 'Close'];
    const legendKey = label => {
      if (label === 'BUY') return 'BUY';
      if (label === 'SELL') return 'SELL';
      if (label.startsWith('VWAP 5')) return 'VWAP 5';
      if (label.startsWith('VWAP 20')) return 'VWAP 20';
      if (label.startsWith('VWAP 200')) return 'VWAP 200';
      return label;
    };
    const annotations = {};

    const config = {
      type: 'line',
      data: {
        labels,
        datasets: [
          {label: 'BUY', data: buyPoints, type: 'line', showLine: false, pointStyle: 'triangle', pointRadius: 7, pointBackgroundColor: '#16a34a', pointBorderColor: '#166534', pointBorderWidth: 1.5, order: 1},
          {label: 'SELL', data: sellPoints, type: 'line', showLine: false, pointStyle: 'triangle', pointRotation: 180, pointRadius: 7, pointBackgroundColor: '#dc2626', pointBorderColor: '#991b1b', pointBorderWidth: 1.5, order: 1},
          {label: 'VWAP 5', data: vwap5, borderColor: '#dc2626', borderWidth: 2.2, borderDash: [5, 3], pointRadius: 0, tension: 0.2, fill: false, order: 3},
          {label: 'VWAP 20', data: vwap20, borderColor: '#16a34a', borderWidth: 2.2, borderDash: [5, 3], pointRadius: 0, tension: 0.2, fill: false, order: 4},
          {label: 'VWAP 200', data: vwap200Line, borderColor: '#2563eb', borderWidth: 2, borderDash: [5, 3], pointRadius: 0, tension: 0, fill: false, order: 5},
          {label: 'Close', data: closes, borderColor: '#64748b', borderWidth: 1, pointRadius: 0, tension: 0.1, fill: false, order: 6}
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: {duration: 200},
        interaction: {mode: 'index', intersect: false},
        plugins: {
          legend: {display: true, labels: {color: '#334155', font: {size: 10}, boxWidth: 12, padding: 10, usePointStyle: true, sort: (a, b) => legendOrder.indexOf(legendKey(a.text)) - legendOrder.indexOf(legendKey(b.text))}},
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
