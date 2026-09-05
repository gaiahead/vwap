const DATA_VERSION = 'data-20260905-1600';
const PRICE_CHART_TRADING_DAYS = 120;
const GRID = '#e2e8f0';
const TICK = '#64748b';
const COLOR = {
  positive: '#16a34a',
  negative: '#dc2626',
  muted: '#64748b',
  blue: '#2563eb'
};
const ALIGNMENT_5_20 = 'alignment_5_20';
const ALIGNMENT_20_60 = 'alignment_20_60';
const ALIGNMENT_60_120 = 'alignment_60_120';
const ALIGNMENT_OPTIONS = [
  { key: ALIGNMENT_5_20 },
  { key: ALIGNMENT_20_60 },
  { key: ALIGNMENT_60_120 }
];
const DEFAULT_SORT = { key: 'name', dir: 'asc' };
const VP_PERIODS = ['1d', '5d', '20d', '60d', '120d'];
const VWAP_LINE_WIDTH = 2;
const PRICE_CHART_EDGE_HIT_WIDTH = 12;
const PRICE_CHART_SELECTION_MARKER_RADIUS = 4;
const PRICE_LINE_DEFS = Object.freeze([
  Object.freeze({ label: '1d', window: 1, color: '#eab308', dash: [], opacity: 0.66 }),
  Object.freeze({ label: '5d', window: 5, color: '#dc2626', dash: [], opacity: 0.72 }),
  Object.freeze({ label: '20d', window: 20, color: '#16a34a', dash: [], opacity: 0.90 }),
  Object.freeze({ label: '60d', window: 60, color: '#2563eb', dash: [], opacity: 0.74 }),
  Object.freeze({ label: '120d', window: 120, color: '#7c3aed', dash: [], opacity: 0.78 })
]);
PRICE_LINE_DEFS.forEach(definition => Object.freeze(definition.dash));
const PRICE_DATASET_ORDER = PRICE_LINE_DEFS.map(def => def.label);

const VWAP_TREND_STYLE_FACTORS = Object.freeze({
  rising: Object.freeze({ opacity: 1.12, width: 1 }),
  flat: Object.freeze({ opacity: 1, width: 1 }),
  falling: Object.freeze({ opacity: 1.12, width: 0.5 })
});

function hasFiniteVwapValue(value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
}

function classifyVwapSegmentState(values, startIndex, endIndex) {
  const startValue = values?.[startIndex];
  const endValue = values?.[endIndex];
  if (!hasFiniteVwapValue(startValue) || !hasFiniteVwapValue(endValue)) return 'flat';
  const numericStart = Number(startValue);
  const numericEnd = Number(endValue);
  if (numericEnd > numericStart) return 'rising';
  if (numericEnd < numericStart) return 'falling';
  return 'flat';
}

function colorWithOpacity(hexColor, opacity) {
  const hex = String(hexColor).replace('#', '');
  const red = parseInt(hex.slice(0, 2), 16);
  const green = parseInt(hex.slice(2, 4), 16);
  const blue = parseInt(hex.slice(4, 6), 16);
  return 'rgba(' + red + ', ' + green + ', ' + blue + ', ' + opacity + ')';
}

function getVwapTrendStyle(period, state = 'flat') {
  const definition = PRICE_LINE_DEFS.find(def => def.window === Number(period));
  if (!definition) return null;
  const normalizedState = VWAP_TREND_STYLE_FACTORS[state] ? state : 'flat';
  const factor = VWAP_TREND_STYLE_FACTORS[normalizedState];
  const opacity = Math.min(1, Number((definition.opacity * factor.opacity).toFixed(3)));
  return Object.freeze({
    state: normalizedState,
    baseColor: definition.color,
    borderColor: colorWithOpacity(definition.color, opacity),
    borderWidth: VWAP_LINE_WIDTH * factor.width,
    opacity
  });
}

function nearestProfileBucketIndex(buckets, price) {
  if (!Array.isArray(buckets) || buckets.length === 0 || !hasFiniteVwapValue(price)) return -1;
  const numericPrice = Number(price);
  let nearestIndex = -1;
  let nearestDistance = Infinity;
  buckets.forEach((bucket, index) => {
    if (!hasFiniteVwapValue(bucket?.price)) return;
    const distance = Math.abs(Number(bucket.price) - numericPrice);
    if (distance < nearestDistance) {
      nearestIndex = index;
      nearestDistance = distance;
    }
  });
  return nearestIndex;
}

function formatPrice(price) {
  if (!hasFiniteVwapValue(price)) return '–';
  return Math.round(Number(price)).toLocaleString('ko-KR', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  });
}

function buildVpAnnotations(detailData, vp) {
  const annotations = {};
  const buckets = vp?.buckets || [];
  const vwapIndex = nearestProfileBucketIndex(buckets, vp?.vwap);
  if (vwapIndex >= 0) {
    annotations.vwapLine = {
      type: 'line',
      scaleID: 'y',
      value: vwapIndex,
      borderColor: COLOR.blue,
      borderWidth: 2,
      label: {
        display: true,
        content: 'VWAP ' + formatPrice(vp.vwap),
        color: '#1d4ed8',
        backgroundColor: 'rgba(255,255,255,0.9)',
        font: { size: 9 },
        position: 'end',
        padding: { x: 3, y: 1 }
      }
    };
  }
  return annotations;
}

function buildPriceChartDateSelection(labels, index) {
  if (!Array.isArray(labels) || !Number.isInteger(index) || index < 0 || index >= labels.length) {
    return null;
  }
  const selectedDate = labels[index];
  if (selectedDate === null || selectedDate === undefined || selectedDate === '') return null;
  return { index, date: selectedDate };
}

function nearestPriceChartIndex(chart, event) {
  const labels = chart?.data?.labels;
  if (!Array.isArray(labels) || labels.length === 0) return -1;
  const { left, right, top, bottom } = chart?.chartArea || {};
  const eventX = event?.x;
  const eventY = event?.y;
  if (![left, right, top, bottom, eventX, eventY].every(Number.isFinite)) return -1;
  if (right <= left || bottom <= top || eventY < top || eventY > bottom) return -1;
  if (eventX < left - PRICE_CHART_EDGE_HIT_WIDTH || eventX > right + PRICE_CHART_EDGE_HIT_WIDTH) {
    return -1;
  }

  const lastIndex = labels.length - 1;
  if (lastIndex === 0) return 0;
  const chartAreaIndex = Math.round(((eventX - left) / (right - left)) * lastIndex);
  return Math.min(lastIndex, Math.max(0, chartAreaIndex));
}

function selectPriceChartIndex(chart, index) {
  const selection = buildPriceChartDateSelection(chart?.data?.labels, index);
  if (!selection) return false;
  const currentSelection = chart.$priceChartDateSelection;
  if (currentSelection?.index === selection.index && currentSelection?.date === selection.date) {
    return false;
  }
  chart.$priceChartDateSelection = selection;
  return true;
}

function drawPriceChartTerminalGridline(chart) {
  const { right, top, bottom } = chart?.chartArea || {};
  if (![right, top, bottom].every(Number.isFinite) || bottom <= top) return;

  const ctx = chart?.ctx;
  if (!ctx || typeof ctx.save !== 'function' || typeof ctx.restore !== 'function') return;

  ctx.save();
  try {
    ctx.strokeStyle = GRID;
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(right, top);
    ctx.lineTo(right, bottom);
    ctx.stroke();
  } finally {
    ctx.restore();
  }
}

function drawPriceChartDateSelection(chart) {
  const currentSelection = chart?.$priceChartDateSelection;
  const selection = buildPriceChartDateSelection(
    chart?.data?.labels,
    currentSelection?.index
  );
  if (!selection || selection.date !== currentSelection.date) return;

  const { left, right, top, bottom } = chart?.chartArea || {};
  if (![left, right, top, bottom].every(Number.isFinite) || right <= left || bottom <= top) {
    return;
  }
  const lastIndex = chart.data.labels.length - 1;
  const selectedX = lastIndex === 0
    ? (left + right) / 2
    : left + ((right - left) * selection.index) / lastIndex;

  const ctx = chart?.ctx;
  if (!ctx || typeof ctx.save !== 'function' || typeof ctx.restore !== 'function') return;

  ctx.save();
  try {
    ctx.strokeStyle = '#000000';
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(selectedX, top);
    ctx.lineTo(selectedX, bottom);
    ctx.stroke();

    const yScale = chart?.scales?.y;
    if (typeof yScale?.getPixelForValue !== 'function') return;
    chart.data.datasets.forEach((dataset, datasetIndex) => {
      const isVisible = typeof chart.isDatasetVisible === 'function'
        ? chart.isDatasetVisible(datasetIndex)
        : dataset.hidden !== true;
      const value = dataset.data?.[selection.index];
      if (!isVisible || !hasFiniteVwapValue(value)) return;
      const y = yScale.getPixelForValue(Number(value));
      if (!Number.isFinite(y) || y < top || y > bottom) return;

      ctx.fillStyle = dataset.borderColor;
      ctx.beginPath();
      ctx.arc(selectedX, y, PRICE_CHART_SELECTION_MARKER_RADIUS, 0, Math.PI * 2);
      ctx.fill();
    });
  } finally {
    ctx.restore();
  }
}

function formatPriceChartDateTick(value) {
  const labels = typeof this?.getLabels === 'function' ? this.getLabels() : [];
  const labelIndex = Number(value);
  if (Number.isInteger(labelIndex) && (
    labelIndex === 0 || labelIndex === labels.length - 1
  )) {
    return '';
  }
  return typeof this?.getLabelForValue === 'function'
    ? this.getLabelForValue(value)
    : value;
}

function buildPriceChartConfig(detailData) {
  const ohlcv = detailData.ohlcv.slice(-PRICE_CHART_TRADING_DAYS);
  const labels = ohlcv.map(day => day.date);
  const vwapLineDatasets = PRICE_LINE_DEFS.map((definition, index) => {
    const values = ohlcv.map(day => day['vwap_' + definition.window + 'd'] ?? null);
    const baseStyle = getVwapTrendStyle(definition.window, 'flat');
    const segmentStyle = context => getVwapTrendStyle(
      definition.window,
      classifyVwapSegmentState(values, context.p0DataIndex, context.p1DataIndex)
    );
    return {
      label: definition.label,
      data: values,
      borderColor: baseStyle.borderColor,
      borderWidth: baseStyle.borderWidth,
      borderDash: definition.dash,
      segment: {
        borderColor: context => segmentStyle(context).borderColor,
        borderWidth: context => segmentStyle(context).borderWidth
      },
      pointStyle: 'line',
      pointRadius: 0,
      tension: 0.2,
      spanGaps: false,
      fill: false,
      order: index + 1
    };
  });
  const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, index) => [label, index]));
  const selectionEvents = new Set(['mousemove', 'click', 'touchstart', 'touchmove']);
  const dateSelectionPlugin = {
    id: 'priceChartDateSelection',
    afterEvent: (chart, args) => {
      const event = args?.event;
      if (!selectionEvents.has(event?.type)) return;
      const index = nearestPriceChartIndex(chart, event);
      if (selectPriceChartIndex(chart, index)) args.changed = true;
    },
    beforeDatasetsDraw: chart => drawPriceChartTerminalGridline(chart),
    afterDatasetsDraw: chart => drawPriceChartDateSelection(chart)
  };
  return {
    type: 'line',
    data: {
      labels,
      datasets: vwapLineDatasets
    },
    plugins: [dateSelectionPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 200 },
      interaction: { mode: 'index', axis: 'x', intersect: false },
      layout: {
        padding: { right: PRICE_CHART_SELECTION_MARKER_RADIUS + 0.5 }
      },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: '#334155',
            font: { size: 10 },
            boxWidth: 28,
            pointStyleWidth: 28,
            padding: 10,
            usePointStyle: true,
            generateLabels: chart => Chart.defaults.plugins.legend.labels.generateLabels(chart).map(item => {
              const dataset = chart.data.datasets[item.datasetIndex] || {};
              return {
                ...item,
                pointStyle: 'line',
                rotation: 0,
                lineDash: dataset.borderDash || [],
                lineWidth: dataset.borderWidth || 1,
                strokeStyle: dataset.borderColor,
                fillStyle: dataset.borderColor
              };
            }),
            sort: (a, b) => (
              (legendOrder.get(a.text) ?? 999) - (legendOrder.get(b.text) ?? 999)
            )
          }
        },
        tooltip: {
          callbacks: {
            label: context => {
              const datasetLabel = context.dataset?.label;
              const formattedPrice = formatPrice(context.parsed?.y);
              return datasetLabel ? datasetLabel + ': ' + formattedPrice : formattedPrice;
            }
          }
        }
      },
      scales: {
        x: {
          ticks: {
            color: TICK,
            font: { size: 9 },
            maxTicksLimit: 12,
            maxRotation: 0,
            callback: formatPriceChartDateTick
          },
          grid: { color: GRID }
        },
        y: {
          ticks: { color: TICK, font: { size: 10 }, callback: formatPrice },
          grid: { color: GRID }
        }
      }
    }
  };
}

const VWAP_CHART_TEST_API = Object.freeze({
  lineDefinitions: PRICE_LINE_DEFS,
  classifyVwapSegmentState,
  getVwapTrendStyle,
  buildVpAnnotations,
  formatPrice,
  buildPriceChartConfig,
  buildPriceChartDateSelection,
  nearestPriceChartIndex,
  selectPriceChartIndex,
  drawPriceChartTerminalGridline,
  drawPriceChartDateSelection
});
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'VWAP_CHART_TEST_API', {
    value: VWAP_CHART_TEST_API,
    writable: false,
    configurable: false,
    enumerable: true
  });
}

const ALIGNMENT_SIGNAL_COLUMNS = ALIGNMENT_OPTIONS.map((option, index) => ({
  key: `signal_${index + 1}`,
  label: `신호 ${index + 1}`,
  type: 'text',
  get: row => row.strategy.strategies?.[option.key]?.latest?.signal
}));
const MOMENTUM_COLUMNS = [
  { key: 'name', label: '종목', type: 'text', get: row => row.name },
  ...ALIGNMENT_SIGNAL_COLUMNS
];
const SORT_FIELDS = Object.fromEntries(MOMENTUM_COLUMNS.map(column => [column.key, column.get]));

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '1d';
let currentDetailName = null;
const detailCache = {};

fetch('trend_data.json?v=' + DATA_VERSION, { cache: 'no-store' }).then(r => r.json()).then(data => {
  const allNames = Object.keys(data).filter(key => key !== '_meta');
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

  function setLoading(message) {
    view.detailContent.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.textContent = message;
    view.detailContent.appendChild(loading);
  }

  function compareRows(a, b) {
    const getter = SORT_FIELDS[sortState.key] || SORT_FIELDS.name;
    const direction = sortState.dir === 'asc' ? 1 : -1;
    const comparison = String(getter(a) ?? '').localeCompare(
      String(getter(b) ?? ''),
      'ko-KR',
      { numeric: true }
    );
    if (comparison !== 0) return comparison * direction;
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
        ? { key, dir: sortState.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' };
      renderMomentum();
    });
    th.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      th.click();
    });
  });

  function renderMomentum() {
    const rows = allNames
      .map(name => ({ name, strategy: data[name]?.strategy_signal }))
      .filter(row => row.strategy?.available)
      .sort(compareRows);
    view.momentumSection.style.display = rows.length ? '' : 'none';
    view.momentumBody.replaceChildren();
    if (!rows.length) return;

    updateSortHeaders();
    rows.forEach(({ name, strategy }) => {
      const ticker = data[name]?.ticker;
      const latestShort = strategy.strategies?.[ALIGNMENT_5_20]?.latest || {};
      const latestMedium = strategy.strategies?.[ALIGNMENT_20_60]?.latest || {};
      const latestLong = strategy.strategies?.[ALIGNMENT_60_120]?.latest || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.append(
        createCell(name),
        createSignalCell(latestShort.signal),
        createSignalCell(latestMedium.signal),
        createSignalCell(latestLong.signal)
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

  function getDetailDisplayName(ticker, name, detailData = null) {
    return detailData?.name || name || ticker;
  }

  function setDetailHeader(ticker, name, detailData = null) {
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
      const response = await fetch(
        'detail_data/' + encodeURIComponent(ticker) + '.json?v=' + DATA_VERSION,
        { cache: 'no-store' }
      );
      if (!response.ok) throw new Error('not found');
      const detail = await response.json();
      detailCache[ticker] = detail;
      renderDetailPanels();
      initVpTabs();
      renderDetail(detail, ticker, name);
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
      button.type = 'button';
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
    tabs.addEventListener('click', event => {
      if (!event.target.matches('.vp-tab')) return;
      currentVpPeriod = event.target.dataset.period;
      document.querySelectorAll('.vp-tab').forEach(button => button.classList.remove('active'));
      event.target.classList.add('active');
      const ticker = data[currentDetailName]?.ticker;
      if (ticker && detailCache[ticker]) renderVpChart(detailCache[ticker], currentVpPeriod);
    });
  }

  function renderDetail(detailData, ticker = detailData.ticker, name = detailData.name) {
    setDetailHeader(ticker, name, detailData);
    renderPriceChart(detailData);
    renderVpChart(detailData, currentVpPeriod);
    view.detailSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function renderPriceChart(detailData) {
    if (priceChart) priceChart.destroy();
    priceChart = new Chart(
      document.getElementById('chart-price'),
      buildPriceChartConfig(detailData)
    );
  }

  function renderVpChart(detailData, period) {
    const vp = detailData.volume_profile[period];
    if (!vp) {
      if (vpChart) vpChart.destroy();
      vpChart = null;
      return;
    }

    const buckets = vp.buckets;
    const labels = buckets.map(bucket => formatPrice(bucket.price));
    const volumes = buckets.map(bucket => bucket.volume);
    const annotations = buildVpAnnotations(detailData, vp);

    const config = {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Volume',
          data: volumes,
          backgroundColor: volumes.map((_, index) => (
            buckets[index].price >= vp.vwap
              ? 'rgba(34,197,94,0.35)'
              : 'rgba(239,68,68,0.32)'
          )),
          borderColor: volumes.map((_, index) => (
            buckets[index].price >= vp.vwap ? '#16a34a' : '#dc2626'
          )),
          borderWidth: 1
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 200 },
        plugins: {
          legend: { display: false },
          annotation: { annotations }
        },
        scales: {
          x: {
            ticks: { color: TICK, font: { size: 9 } },
            grid: { color: GRID }
          },
          y: {
            reverse: true,
            ticks: { color: TICK, font: { size: 8 } },
            grid: { color: GRID }
          }
        }
      }
    };

    if (vpChart) vpChart.destroy();
    vpChart = new Chart(document.getElementById('chart-vp'), config);
  }

  renderMomentum();

  function handleHash() {
    const hash = decodeURIComponent(location.hash.slice(1));
    if (!hash) return;
    const matched = allNames.find(name => data[name]?.ticker === hash);
    if (matched) fetchDetail(hash, matched);
  }
  handleHash();
});
