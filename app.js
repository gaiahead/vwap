const DATA_VERSION = 'refactor-20260602';
const GRID = '#e2e8f0';
const TICK = '#64748b';
const COLOR = {
  positive: '#16a34a',
  negative: '#dc2626',
  muted: '#64748b',
  neutral: '#475569',
  blue: '#2563eb'
};
const DEFAULT_SORT = { key: 'vwap_5_20_return_pct', dir: 'desc' };
const VP_PERIODS = ['5d', '20d', '200d'];
const PRICE_DATASET_ORDER = ['BUY', 'SELL', 'VWAP 5', 'VWAP 20', 'VWAP 200', 'Close'];

const MOMENTUM_COLUMNS = [
  { key: 'name', label: '종목', type: 'text', get: row => row.name },
  { key: 'last_signal_date', label: '최근 변화', type: 'text', get: row => row.strategy.latest?.last_signal_date || '' },
  { key: 'vwap_5_20_return_pct', label: '5/20 수익률', type: 'number', get: row => row.strategy.latest?.vwap_5_20_return_pct },
  { key: 'vwap_5_200_return_pct', label: '5/200 수익률', type: 'number', get: row => row.strategy.latest?.vwap_5_200_return_pct },
  { key: 'holding_days', label: '당기 보유일', type: 'number', get: row => row.strategy.latest?.holding_days },
  { key: 'current_trade_return_pct', label: '당기 수익률', type: 'number', get: row => row.strategy.latest?.current_trade_return_pct },
  { key: 'strategy_return_pct', label: '200일 전략 수익률', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.strategy_return_pct },
  { key: 'buy_hold_return_pct', label: '200일 보유 수익률', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.buy_hold_return_pct },
  { key: 'strategy_mdd_pct', label: '200일 전략 MDD', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.strategy_mdd_pct, isMdd: true },
  { key: 'buy_hold_mdd_pct', label: '200일 보유 MDD', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.buy_hold_mdd_pct, isMdd: true }
];
const SORT_FIELDS = Object.fromEntries(MOMENTUM_COLUMNS.map(column => [column.key, column.get]));
const NUMERIC_SORT_FIELDS = new Set(MOMENTUM_COLUMNS.filter(column => column.type === 'number').map(column => column.key));
const DETAIL_NAME_OVERRIDES = {
  TLT: 'iShares 20+ Year Treasury Bond ETF',
  GLD: 'SPDR Gold Shares',
  IBIT: 'iShares Bitcoin Trust ETF',
  SPY: 'State Street SPDR S&P 500 ETF Trust',
  QQQ: 'Invesco QQQ Trust',
  SCHD: 'Schwab U.S. Dividend Equity ETF',
  XLE: 'State Street Energy Select Sector SPDR ETF',
  GUNR: 'FlexShares Morningstar Global Upstream Natural Resources Index Fund',
  IXC: 'iShares Global Energy ETF',
  XOP: 'State Street SPDR S&P Oil & Gas Exploration & Production ETF',
  OIH: 'VanEck Oil Services ETF',
  SLB: 'SLB N.V.',
  UPRO: 'ProShares UltraPro S&P500',
  RSP: 'Invesco S&P 500 Equal Weight ETF',
  IWM: 'iShares Russell 2000 ETF',
  IEF: 'iShares 7-10 Year Treasury Bond ETF',
  SHY: 'iShares 1-3 Year Treasury Bond ETF',
  TIP: 'iShares TIPS Bond ETF',
  HYG: 'iShares iBoxx $ High Yield Corporate Bond ETF',
  LQD: 'iShares iBoxx $ Investment Grade Corporate Bond ETF',
  UUP: 'Invesco DB US Dollar Index Bullish Fund',
  FXY: 'Invesco CurrencyShares Japanese Yen Trust',
  XLK: 'State Street Technology Select Sector SPDR ETF',
  ITA: 'iShares U.S. Aerospace & Defense ETF',
  XAR: 'State Street SPDR S&P Aerospace & Defense ETF',
  RTX: 'RTX Corporation',
  XLF: 'State Street Financial Select Sector SPDR ETF',
  XLV: 'State Street Health Care Select Sector SPDR ETF',
  XLI: 'State Street Industrial Select Sector SPDR ETF',
  XLY: 'State Street Consumer Discretionary Select Sector SPDR ETF',
  XLP: 'State Street Consumer Staples Select Sector SPDR ETF',
  XLU: 'State Street Utilities Select Sector SPDR ETF',
  XLRE: 'State Street Real Estate Select Sector SPDR ETF',
  XLB: 'State Street Materials Select Sector SPDR ETF',
  USO: 'United States Oil Fund, LP',
  UCO: 'ProShares Ultra Bloomberg Crude Oil',
  NUGT: 'Direxion Daily Gold Miners Index Bull 2X Shares',
  CPER: 'United States Copper Index Fund, LP',
  COPX: 'Global X Copper Miners ETF',
  DBA: 'Invesco DB Agriculture Fund',
  URA: 'Global X Uranium ETF',
  SLV: 'iShares Silver Trust',
  EFA: 'iShares MSCI EAFE ETF',
  EEM: 'iShares MSCI Emerging Markets ETF',
  EWJ: 'iShares MSCI Japan ETF',
  FXI: 'iShares China Large-Cap ETF',
  INDA: 'iShares MSCI India ETF',
  EWT: 'iShares MSCI Taiwan ETF',
  TQQQ: 'ProShares UltraPro QQQ',
  SOXL: 'Direxion Daily Semiconductor Bull 3X Shares',
  TECL: 'Direxion Daily Technology Bull 3X Shares',
  ASML: 'ASML Holding N.V.',
  TCAI: 'Tortoise AI Infrastructure ETF',
  PANW: 'Palo Alto Networks, Inc.',
  FTNT: 'Fortinet, Inc.',
  DDOG: 'Datadog, Inc.',
  CRWD: 'CrowdStrike Holdings, Inc.'
};

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '20d';
let currentDetailName = null;
const detailCache = {};

fetch(`trend_data.json?v=${DATA_VERSION}`, { cache: 'no-store' }).then(r=>r.json()).then(data=>{
  const allNames = Object.keys(data).filter(k => k !== '_meta');

  document.getElementById('updated').textContent =
    (data._meta?.updated_at || '') + ' 기준';

  // ─── Formatting helpers ──────────────────────────────────────────
  function fmtPct(v) { return v == null ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`; }
  function statColor(value, isMdd=false) {
    if (value == null) return COLOR.muted;
    if (isMdd) return value <= -20 ? COLOR.negative : COLOR.positive;
    return value >= 0 ? COLOR.positive : COLOR.negative;
  }
  function signalColor(type) {
    if (type === 'BUY') return COLOR.positive;
    if (type === 'SELL') return COLOR.negative;
    return COLOR.muted;
  }

  function createCell(text, { className, color, weight } = {}) {
    const td = document.createElement('td');
    td.textContent = text;
    if (className) td.className = className;
    if (color) td.style.color = color;
    if (weight) td.style.fontWeight = weight;
    return td;
  }

  function createNameCell(name) {
    const td = document.createElement('td');
    const indicator = document.createElement('span');
    indicator.className = 'row-indicator';
    td.append(indicator, document.createTextNode(name));
    return td;
  }

  function setLoading(text) {
    detailContent.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.textContent = text;
    detailContent.appendChild(loading);
  }

  let sortState = { ...DEFAULT_SORT };

  function compareRows(a, b) {
    const getter = SORT_FIELDS[sortState.key] || SORT_FIELDS.current_trade_return_pct;
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
    const targets = ['삼성전자','SK하이닉스','한미반도체','리노공업'];
    const hasMomentumTargets = targets.some(n => data[n]);
    if (!hasMomentumTargets) return;

    document.getElementById('momentum-section').style.display = '';
    const tbody = document.getElementById('momentum-body');
    tbody.replaceChildren();

    const rows = allNames
      .map(n => ({ name: n, strategy: data[n]?.strategy_signal }))
      .filter(r => r.strategy?.available)
      .sort(compareRows);
    updateSortHeaders();

    rows.forEach(({name, strategy}) => {
      const ticker = data[name]?.ticker;
      const latest = strategy?.latest || {};
      const trendColor = statColor(latest.vwap_5_200_return_pct);
      const rolling200 = strategy?.backtest?.rolling_200d || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.style.setProperty('--c', trendColor);
      tr.append(
        createNameCell(name),
        createCell(
          `${latest.last_signal || '–'} ${latest.last_signal_date ? latest.last_signal_date.slice(5) : ''}`,
          { className: 'recent-signal', color: signalColor(latest.last_signal), weight: '800' }
        ),
        createCell(fmtPct(latest.vwap_5_20_return_pct), { color: statColor(latest.vwap_5_20_return_pct), weight: '800' }),
        createCell(fmtPct(latest.vwap_5_200_return_pct), { color: statColor(latest.vwap_5_200_return_pct), weight: '800' }),
        createCell(latest.holding_days ?? '–'),
        createCell(fmtPct(latest.current_trade_return_pct), { color: statColor(latest.current_trade_return_pct), weight: '800' }),
        createCell(fmtPct(rolling200.strategy_return_pct), { color: statColor(rolling200.strategy_return_pct), weight: '800' }),
        createCell(fmtPct(rolling200.buy_hold_return_pct), { color: statColor(rolling200.buy_hold_return_pct), weight: '800' }),
        createCell(fmtPct(rolling200.strategy_mdd_pct), { color: statColor(rolling200.strategy_mdd_pct, true), weight: '800' }),
        createCell(fmtPct(rolling200.buy_hold_mdd_pct), { color: statColor(rolling200.buy_hold_mdd_pct, true), weight: '800' })
      );
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
  const detailSymbol = document.getElementById('detail-symbol');

  function getDetailDisplayName(ticker, name, detailData=null) {
    return DETAIL_NAME_OVERRIDES[ticker] || detailData?.name || name || ticker;
  }

  function setDetailHeader(ticker, name, detailData=null) {
    const displayName = getDetailDisplayName(ticker, name, detailData);
    detailTitle.textContent = displayName;
    detailSymbol.textContent = ticker && ticker !== displayName ? ticker : '';
  }

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
    const heading = document.createElement('div');
    heading.className = 'panel-title';
    heading.textContent = title;
    const chartWrap = document.createElement('div');
    chartWrap.className = 'chart-wrap';
    const canvas = document.createElement('canvas');
    canvas.id = canvasId;
    chartWrap.appendChild(canvas);
    panel.append(heading, chartWrap);
    return panel;
  }

  function renderDetailPanels() {
    const pricePanel = createChartPanel('VWAP Lines · 5/20/200', 'chart-price');
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
    detailContent.replaceChildren(pricePanel, vpPanel);
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
          legend: {display: true, labels: {color: '#334155', font: {size: 10}, boxWidth: 12, padding: 10, usePointStyle: true, sort: (a, b) => PRICE_DATASET_ORDER.indexOf(legendKey(a.text)) - PRICE_DATASET_ORDER.indexOf(legendKey(b.text))}},
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
