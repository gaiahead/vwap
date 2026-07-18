const DATA_VERSION = 'code-refactor-20260718';
const GRID = '#e2e8f0';
const TICK = '#64748b';
const COLOR = {
  positive: '#16a34a',
  negative: '#dc2626',
  muted: '#64748b',
  blue: '#2563eb'
};
const DEFAULT_SORT = { key: 'strategy_return_pct', dir: 'desc' };
const VP_PERIODS = ['1d', '5d', '20d', '200d'];
const PRICE_LINE_DEFS = [
  { label: '1d', window: 1, color: '#eab308', dash: [], width: 1.15 },
  { label: '5d', window: 5, color: '#dc2626', dash: [], width: 1.15 },
  { label: '20d', window: 20, color: '#16a34a', dash: [], width: 1.15 },
  { label: '200d', window: 200, color: '#000000', dash: [], width: 1.15 }
];
const PRICE_DATASET_ORDER = ['BUY', 'SELL', ...PRICE_LINE_DEFS.map(def => def.label)];

const MOMENTUM_COLUMNS = [
  { key: 'name', label: '종목', type: 'text', get: row => row.name },
  { key: 'signal', label: '신호', type: 'text', get: row => row.strategy.latest?.signal },
  { key: 'strategy_return_pct', label: '정배열 수익률', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.strategy_return_pct },
  { key: 'buy_hold_return_pct', label: '200일 수익률', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.buy_hold_return_pct }
];
const SORT_FIELDS = Object.fromEntries(MOMENTUM_COLUMNS.map(column => [column.key, column.get]));
const NUMERIC_SORT_FIELDS = new Set(MOMENTUM_COLUMNS.filter(column => column.type === 'number').map(column => column.key));

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '1d';
let currentDetailName = null;
const detailCache = {};

fetch(`trend_data.json?v=${DATA_VERSION}`, { cache: 'no-store' }).then(r=>r.json()).then(data=>{
  const allNames = Object.keys(data).filter(k => k !== '_meta');
  const view = {
    updated: document.getElementById('updated'),
    momentumSection: document.getElementById('momentum-section'),
    momentumBody: document.getElementById('momentum-body'),
    detailSection: document.getElementById('detail-section'),
    detailContent: document.getElementById('detail-content'),
    detailTitle: document.getElementById('detail-title'),
    detailSymbol: document.getElementById('detail-symbol'),
    detailClose: document.getElementById('detail-close')
  };
  let sortState = { ...DEFAULT_SORT };

  view.updated.textContent = (data._meta?.updated_at || '') + ' 기준';

  // ─── Formatting helpers ──────────────────────────────────────────
  function fmtPct(v) { return v == null ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`; }
  function statColor(value) {
    if (value == null) return COLOR.muted;
    return value >= 0 ? COLOR.positive : COLOR.negative;
  }
  function createCell(text, { className, color, weight } = {}) {
    const td = document.createElement('td');
    td.textContent = text;
    if (className) td.className = className;
    if (color) td.style.color = color;
    if (weight) td.style.fontWeight = weight;
    return td;
  }

  function createSignalCell(signal) {
    if (signal === 'BUY') return createCell('BUY', { className: 'signal-cell buy', color: COLOR.positive, weight: '900' });
    if (signal === 'SELL') return createCell('SELL', { className: 'signal-cell sell', color: COLOR.negative, weight: '900' });
    return createCell('–', { className: 'signal-cell wait', color: COLOR.muted, weight: '800' });
  }


  function setLoading(text) {
    view.detailContent.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.textContent = text;
    view.detailContent.appendChild(loading);
  }

  function compareRows(a, b) {
    const getter = SORT_FIELDS[sortState.key] || SORT_FIELDS.strategy_return_pct;
    const av = getter(a);
    const bv = getter(b);
    const dir = sortState.dir === 'asc' ? 1 : -1;
    if (NUMERIC_SORT_FIELDS.has(sortState.key)) {
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
        : { key, dir: NUMERIC_SORT_FIELDS.has(key) ? 'desc' : 'asc' };
      renderMomentum();
    });
    th.addEventListener('keydown', e => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      e.preventDefault();
      th.click();
    });
  });

  function renderMomentum() {
    const rows = allNames
      .map(n => ({ name: n, strategy: data[n]?.strategy_signal }))
      .filter(r => r.strategy?.available)
      .sort(compareRows);
    view.momentumSection.style.display = rows.length ? '' : 'none';
    view.momentumBody.replaceChildren();
    if (!rows.length) return;

    updateSortHeaders();

    rows.forEach(({name, strategy}) => {
      const ticker = data[name]?.ticker;
      const latest = strategy?.latest || {};
      const rolling200 = strategy?.backtest?.rolling_200d || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.append(
        createCell(name),
        createSignalCell(latest.signal),
        createCell(fmtPct(rolling200.strategy_return_pct), { color: statColor(rolling200.strategy_return_pct), weight: '800' }),
        createCell(fmtPct(rolling200.buy_hold_return_pct), { color: statColor(rolling200.buy_hold_return_pct), weight: '800' })
      );
      tr.addEventListener('click', () => {
        if (!ticker) return;
        currentVpPeriod = '1d';
        location.hash = encodeURIComponent(ticker);
        fetchDetail(ticker, name);
      });
      view.momentumBody.appendChild(tr);
    });
  }

  // ─── Detail section ────────────────────────────────────
  function getDetailDisplayName(ticker, name, detailData=null) {
    return detailData?.name || name || ticker;
  }

  function setDetailHeader(ticker, name, detailData=null) {
    const displayName = getDetailDisplayName(ticker, name, detailData);
    view.detailTitle.textContent = displayName;
    view.detailSymbol.textContent = ticker && ticker !== displayName ? ticker : '';
  }

  view.detailClose.addEventListener('click', () => {
    view.detailSection.style.display = 'none';
    currentDetailName = null;
    location.hash = '';
    renderMomentum();
  });

  async function fetchDetail(ticker, name) {
    view.detailSection.style.display = '';
    currentDetailName = name;
    renderMomentum();

    if (detailCache[ticker]) {
      if (!document.getElementById('chart-price') || !document.getElementById('chart-vp')) {
        renderDetailPanels();
        initVpTabs();
      }
      renderDetail(detailCache[ticker], ticker, name);
      return;
    }

    setLoading('Loading...');
    setDetailHeader(ticker, name);

    try {
      const resp = await fetch(`detail_data/${encodeURIComponent(ticker)}.json?v=${DATA_VERSION}`, { cache: 'no-store' });
      if (!resp.ok) throw new Error('not found');
      const json = await resp.json();
      detailCache[ticker] = json;
      renderDetailPanels();
      initVpTabs();
      renderDetail(json, ticker, name);
    } catch {
      setLoading('Data not available');
    }
  }

  function createChartPanel(title, canvasId) {
    const panel = document.createElement('div');
    panel.className = 'panel-box';
    const chartWrap = document.createElement('div');
    chartWrap.className = 'chart-wrap';
    const canvas = document.createElement('canvas');
    canvas.id = canvasId;
    chartWrap.appendChild(canvas);
    if (title) {
      const heading = document.createElement('div');
      heading.className = 'panel-title';
      heading.textContent = title;
      panel.appendChild(heading);
    }
    panel.appendChild(chartWrap);
    return panel;
  }

  function renderDetailPanels() {
    const pricePanel = createChartPanel('', 'chart-price');
    const vpPanel = createChartPanel('Volume Profile', 'chart-vp');
    vpPanel.classList.add('volume-profile-panel');

    const tabs = document.createElement('div');
    tabs.className = 'vp-tabs';
    tabs.id = 'vp-tabs';
    VP_PERIODS.forEach(period => {
      const button = document.createElement('button');
      button.className = 'vp-tab' + (period === currentVpPeriod ? ' active' : '');
      button.dataset.period = period;
      button.textContent = period;
      tabs.appendChild(button);
    });
    vpPanel.insertBefore(tabs, vpPanel.querySelector('.chart-wrap'));
    view.detailContent.replaceChildren(pricePanel, vpPanel);
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

  function renderDetail(detailData, ticker=detailData.ticker, name=detailData.name) {
    setDetailHeader(ticker, name, detailData);
    renderPriceChart(detailData);
    renderVpChart(detailData, currentVpPeriod);
    view.detailSection.scrollIntoView({behavior:'smooth', block:'start'});
  }

  // ─── Panel A: Price + VWAP ─────────────────────────────
  function renderPriceChart(detailData) {
    const ohlcv = detailData.ohlcv;
    const labels = ohlcv.map(d => d.date);
    const signalMap = new Map((detailData.strategy_signal?.signals || []).map(signal => [signal.date, signal]));
    const markerData = type => labels.map((date, i) => {
      const signal = signalMap.get(date);
      if (signal?.type !== type) return null;
      return signal.marker_price ?? ohlcv[i]?.vwap_5d ?? null;
    });
    const lineData = def => ohlcv.map(d => d[`vwap_${def.window}d`] ?? null);
    const vwapLineDatasets = PRICE_LINE_DEFS.map((def, idx) => ({
      label: def.label,
      data: lineData(def),
      borderColor: def.color,
      borderWidth: def.width,
      borderDash: def.dash,
      pointStyle: 'line',
      pointRadius: 0,
      tension: 0.2,
      fill: false,
      order: idx + 2
    }));
    const signalDatasets = [
      { label: 'BUY', data: markerData('BUY'), type: 'line', showLine: false, pointStyle: 'triangle', pointRotation: 0, pointRadius: 7, pointHoverRadius: 9, pointBackgroundColor: COLOR.positive, pointBorderColor: '#166534', pointBorderWidth: 1.5, order: 1 },
      { label: 'SELL', data: markerData('SELL'), type: 'line', showLine: false, pointStyle: 'triangle', pointRotation: 180, pointRadius: 7, pointHoverRadius: 9, pointBackgroundColor: COLOR.negative, pointBorderColor: '#991b1b', pointBorderWidth: 1.5, order: 1 }
    ];
    const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, idx) => [label, idx]));

    const config = {
      type: 'line',
      data: {
        labels,
        datasets: [...signalDatasets, ...vwapLineDatasets]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: {duration: 200},
        interaction: {mode: 'index', intersect: false},
        plugins: {
          legend: {display: true, labels: {
            color: '#334155', font: {size: 10}, boxWidth: 28, pointStyleWidth: 28, padding: 10, usePointStyle: true,
            generateLabels: chart => Chart.defaults.plugins.legend.labels.generateLabels(chart).map(item => {
              const dataset = chart.data.datasets[item.datasetIndex] || {};
              const isSignal = dataset.label === 'BUY' || dataset.label === 'SELL';
              return {
                ...item,
                pointStyle: isSignal ? dataset.pointStyle : 'line',
                rotation: isSignal ? dataset.pointRotation : 0,
                lineDash: dataset.borderDash || [],
                lineWidth: dataset.borderWidth || 1,
                strokeStyle: dataset.borderColor || dataset.pointBorderColor,
                fillStyle: dataset.pointBackgroundColor || dataset.borderColor
              };
            }),
            sort: (a, b) => (legendOrder.get(a.text) ?? 999) - (legendOrder.get(b.text) ?? 999)
          }},
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
        borderColor: COLOR.blue, borderWidth: 2,
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
