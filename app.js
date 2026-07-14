const DATA_VERSION = 'fix-leeno-20260714';
const GRID = '#e2e8f0';
const TICK = '#64748b';
const COLOR = {
  positive: '#16a34a',
  negative: '#dc2626',
  muted: '#64748b',
  neutral: '#475569',
  warning: '#ea580c',
  blue: '#2563eb'
};
const DEFAULT_SORT = { key: 'vwap_5_20_return_pct', dir: 'desc' };
const VP_PERIODS = ['2d', '5d', '20d', '40d', '60d', '100d', '200d'];
const PRICE_LINE_DEFS = [
  { label: '2d', window: 2, color: '#eab308', dash: [], width: 1.15 },
  { label: '5d', window: 5, color: '#dc2626', dash: [], width: 1.15 },
  { label: '20d', window: 20, color: '#16a34a', dash: [], width: 1.15 },
  { label: '40d', window: 40, color: '#0891b2', dash: [], width: 1.15 },
  { label: '60d', window: 60, color: '#2563eb', dash: [], width: 1.15 },
  { label: '100d', window: 100, color: '#1e3a8a', dash: [], width: 1.15 },
  { label: '200d', window: 200, color: '#000000', dash: [], width: 1.15, horizontal: true }
];
const PRICE_DATASET_ORDER = PRICE_LINE_DEFS.map(def => def.label);

const MOMENTUM_COLUMNS = [
  { key: 'name', label: '종목', type: 'text', get: row => row.name },
  { key: 'ea_score', label: 'EA지수', type: 'number', get: row => row.lifecycle?.ea },
  { key: 'lm_score', label: 'LM지수', type: 'number', get: row => row.lifecycle?.lm },
  { key: 'vwap_5_20_return_pct', label: '5/20 괴리율', type: 'number', get: row => row.strategy.latest?.vwap_5_20_return_pct },
  { key: 'vwap_5_200_return_pct', label: '5/200 괴리율', type: 'number', get: row => row.strategy.latest?.vwap_5_200_return_pct },
  { key: 'buy_hold_return_pct', label: '200일 수익률', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.buy_hold_return_pct },
  { key: 'buy_hold_mdd_pct', label: '200일 MDD', type: 'number', get: row => row.strategy.backtest?.rolling_200d?.buy_hold_mdd_pct, isMdd: true }
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
  MRVL: 'Marvell Technology, Inc.',
  SNDK: 'Sandisk Corporation',
  ASML: 'ASML Holding N.V.',
  TCAI: 'Tortoise AI Infrastructure ETF',
  PANW: 'Palo Alto Networks, Inc.',
  FTNT: 'Fortinet, Inc.',
  DDOG: 'Datadog, Inc.',
  CRWD: 'CrowdStrike Holdings, Inc.'
};

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '2d';
let currentDetailName = null;
const detailCache = {};

fetch(`trend_data.json?v=${DATA_VERSION}`, { cache: 'no-store' }).then(r=>r.json()).then(data=>{
  const allNames = Object.keys(data).filter(k => k !== '_meta');

  document.getElementById('updated').textContent =
    (data._meta?.updated_at || '') + ' 기준';

  // ─── Formatting helpers ──────────────────────────────────────────
  function fmtPct(v) { return v == null ? '–' : `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%`; }
  function fmtIndex(v) { return v == null ? '–' : `${Math.round(Number(v))}%`; }
  function statColor(value, isMdd=false) {
    if (value == null) return COLOR.muted;
    if (isMdd) return value <= -20 ? COLOR.negative : COLOR.positive;
    return value >= 0 ? COLOR.positive : COLOR.negative;
  }
  function indexColor(value, kind) {
    if (value == null) return COLOR.muted;
    if (kind === 'lm') {
      if (value >= 70) return COLOR.negative;
      if (value >= 45) return COLOR.warning;
      return COLOR.muted;
    }
    if (value >= 65) return COLOR.positive;
    if (value >= 40) return COLOR.blue;
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
    td.textContent = name;
    return td;
  }

  function finite(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function clamp01(value) {
    return Math.max(0, Math.min(1, value));
  }

  function ramp(value, low, high) {
    const number = finite(value);
    if (number == null || high === low) return null;
    return clamp01((number - low) / (high - low));
  }

  function fadeAbove(value, low, high) {
    const score = ramp(value, low, high);
    return score == null ? null : 1 - score;
  }

  function bandScore(value, goodLow, goodHigh, badLow, badHigh) {
    const number = finite(value);
    if (number == null) return null;
    if (number < goodLow) return ramp(number, badLow, goodLow);
    if (number > goodHigh) return fadeAbove(number, goodHigh, badHigh);
    return 1;
  }

  function weightedAverage(parts) {
    let total = 0;
    let weightTotal = 0;
    parts.forEach(([score, weight]) => {
      const value = finite(score);
      if (value == null) return;
      total += clamp01(value) * weight;
      weightTotal += weight;
    });
    return weightTotal > 0 ? total / weightTotal : null;
  }

  function weightedIndex(parts) {
    const score = weightedAverage(parts);
    return score == null ? null : Math.round(score * 100);
  }

  function maxScore(scores) {
    const values = scores.map(finite).filter(value => value != null);
    return values.length ? Math.max(...values) : null;
  }

  function pctRatio(numerator, denominator) {
    const n = finite(numerator);
    const d = finite(denominator);
    if (n == null || d == null || d === 0) return null;
    return (n / d - 1) * 100;
  }

  function getVwap(item, window) {
    const found = item?.vwap_structure?.find(entry => Number(entry.window) === window);
    return finite(found?.vwap);
  }

  function calculateLifecycleScores(item) {
    const latest = item?.strategy_signal?.latest || {};
    const rolling200 = item?.strategy_signal?.backtest?.rolling_200d || {};
    const lastRecord = item?.records?.at(-1) || {};
    const vwap2 = getVwap(item, 2);
    const vwap5 = finite(latest.vwap5) ?? getVwap(item, 5);
    const vwap20 = finite(latest.vwap20) ?? getVwap(item, 20);
    const vwap40 = getVwap(item, 40);
    const vwap60 = getVwap(item, 60);
    const vwap200 = finite(latest.vwap200) ?? getVwap(item, 200);
    const price = finite(lastRecord.price);

    const spread2_5 = pctRatio(vwap2, vwap5);
    const spread5_20 = finite(latest.vwap_5_20_return_pct) ?? pctRatio(vwap5, vwap20);
    const spread5_200 = finite(latest.vwap_5_200_return_pct) ?? pctRatio(vwap5, vwap200);
    const spread20_40 = pctRatio(vwap20, vwap40);
    const spread20_60 = pctRatio(vwap20, vwap60);
    const spread20_200 = pctRatio(vwap20, vwap200);
    const priceVs5 = pctRatio(price, vwap5);
    const priceVs20 = pctRatio(price, vwap20);
    const priceVs200 = pctRatio(price, vwap200);
    const currentTrade = finite(latest.current_trade_return_pct);
    const holdingDays = finite(latest.holding_days);
    const buyHold = finite(rolling200.buy_hold_return_pct);

    const activationRise = ramp(spread5_20, 0, 2);
    const activationNotOverextended = fadeAbove(spread5_20, 7, 15);
    const activation = activationRise == null || activationNotOverextended == null
      ? null
      : activationRise * activationNotOverextended;
    const priceReclaimRise = ramp(priceVs20, -0.5, 2);
    const priceReclaimNotOverextended = fadeAbove(priceVs20, 8, 16);
    const priceReclaim = priceReclaimRise == null || priceReclaimNotOverextended == null
      ? null
      : priceReclaimRise * priceReclaimNotOverextended;
    const overheatControl = bandScore(spread5_200, -2, 18, -12, 42);
    const longContextGate = weightedAverage([
      [ramp(spread5_200, -6, 5), 0.35],
      [ramp(priceVs200, -6, 5), 0.25],
      [ramp(spread20_200, -8, 6), 0.25],
      [ramp(buyHold, -12, 12), 0.15]
    ]);
    const tradeFresh = currentTrade == null
      ? (finite(spread5_20) != null && spread5_20 > 0 ? 0.85 : 0)
      : weightedAverage([
        [bandScore(currentTrade, -4, 10, -12, 28), 0.6],
        [holdingDays == null ? null : fadeAbove(holdingDays, 18, 70), 0.4]
      ]);
    const earlyAcceleration = weightedAverage([
      [bandScore(spread2_5, 0, 5, -3, 12), 0.55],
      [bandScore(spread20_40, -2, 8, -8, 18), 0.2],
      [bandScore(priceVs5, -2, 5, -8, 14), 0.25]
    ]);
    const eaRaw = weightedAverage([
      [activation, 0.32],
      [priceReclaim, 0.22],
      [overheatControl, 0.18],
      [tradeFresh, 0.16],
      [earlyAcceleration, 0.12]
    ]);
    const eaGate = weightedAverage([
      [activation, 0.6],
      [priceReclaim, 0.4]
    ]);
    const ea = eaRaw == null || eaGate == null || longContextGate == null
      ? null
      : Math.round(eaRaw * eaGate * (0.15 + 0.85 * longContextGate) * 100);

    const maturity = weightedAverage([
      [ramp(spread20_200, 12, 40), 0.35],
      [ramp(spread5_200, 18, 55), 0.35],
      [ramp(priceVs200, 15, 55), 0.3]
    ]);
    const mediumTrendLead = maxScore([spread20_60, spread20_40, spread20_200]);
    const deceleration = weightedAverage([
      [ramp(mediumTrendLead != null && spread5_20 != null ? mediumTrendLead - spread5_20 : null, 4, 20), 0.35],
      [ramp(spread2_5 == null ? null : -spread2_5, 0.5, 6), 0.2],
      [ramp(priceVs5 == null ? null : -priceVs5, 0.5, 7), 0.2],
      [ramp(priceVs20 == null ? null : -priceVs20, 2, 14), 0.25]
    ]);
    const harvest = maxScore([
      ramp(currentTrade, 10, 35),
      ramp(holdingDays, 25, 90),
      ramp(buyHold, 20, 90),
      ramp(spread5_200, 25, 70)
    ]);
    const notBroken = weightedAverage([
      [ramp(spread20_200, 8, 22), 0.55],
      [priceVs20 == null ? null : fadeAbove(-priceVs20, 18, 35), 0.3],
      [spread5_200 == null ? null : fadeAbove(-spread5_200, 0, 15), 0.15]
    ]);
    const lm = weightedIndex([
      [maturity, 0.32],
      [deceleration, 0.32],
      [harvest, 0.22],
      [notBroken, 0.14]
    ]);

    return { ea, lm };
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
    const getter = SORT_FIELDS[sortState.key] || SORT_FIELDS.vwap_5_20_return_pct;
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
      .map(n => ({ name: n, strategy: data[n]?.strategy_signal, lifecycle: calculateLifecycleScores(data[n]) }))
      .filter(r => r.strategy?.available)
      .sort(compareRows);
    updateSortHeaders();

    rows.forEach(({name, strategy, lifecycle}) => {
      const ticker = data[name]?.ticker;
      const latest = strategy?.latest || {};
      const rolling200 = strategy?.backtest?.rolling_200d || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.append(
        createNameCell(name),
        createCell(fmtIndex(lifecycle.ea), { color: indexColor(lifecycle.ea, 'ea'), weight: '800' }),
        createCell(fmtIndex(lifecycle.lm), { color: indexColor(lifecycle.lm, 'lm'), weight: '800' }),
        createCell(fmtPct(latest.vwap_5_20_return_pct), { color: statColor(latest.vwap_5_20_return_pct), weight: '800' }),
        createCell(fmtPct(latest.vwap_5_200_return_pct), { color: statColor(latest.vwap_5_200_return_pct), weight: '800' }),
        createCell(fmtPct(rolling200.buy_hold_return_pct), { color: statColor(rolling200.buy_hold_return_pct), weight: '800' }),
        createCell(fmtPct(rolling200.buy_hold_mdd_pct), { color: statColor(rolling200.buy_hold_mdd_pct, true), weight: '800' })
      );
      tr.addEventListener('click', () => {
        if (!ticker) return;
        currentVpPeriod = '2d';
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
  function rollingProxyVwap(ohlcv, windowSize) {
    return ohlcv.map((_, i) => {
      if (i < windowSize - 1) return null;
      const rows = ohlcv.slice(i - windowSize + 1, i + 1);
      let pvSum = 0;
      let volumeSum = 0;
      for (const row of rows) {
        const vwap1d = Number(row.vwap_1d ?? ((row.high + row.low + row.close) / 3));
        const volume = Number(row.volume);
        if (!Number.isFinite(vwap1d) || !Number.isFinite(volume)) return null;
        pvSum += vwap1d * volume;
        volumeSum += volume;
      }
      return volumeSum > 0 ? pvSum / volumeSum : null;
    });
  }

  function renderPriceChart(detailData) {
    const ohlcv = detailData.ohlcv;
    const labels = ohlcv.map(d => d.date);
    const vp = detailData.volume_profile;
    const lineData = def => {
      if (def.horizontal) {
        const vwap = vp?.[`${def.window}d`]?.vwap ?? null;
        return labels.map(() => vwap);
      }
      return ohlcv.map(d => d[`vwap_${def.window}d`] ?? null).some(v => v != null)
        ? ohlcv.map(d => d[`vwap_${def.window}d`] ?? null)
        : rollingProxyVwap(ohlcv, def.window);
    };
    const vwapLineDatasets = PRICE_LINE_DEFS.map((def, idx) => ({
      label: def.label,
      data: lineData(def),
      borderColor: def.color,
      borderWidth: def.width,
      borderDash: def.dash,
      pointStyle: 'line',
      pointRadius: 0,
      tension: def.horizontal ? 0 : 0.2,
      fill: false,
      order: idx + 2
    }));
    const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, idx) => [label, idx]));
    const legendKey = label => legendOrder.has(label) ? label : label;
    const annotations = {};

    const config = {
      type: 'line',
      data: {
        labels,
        datasets: vwapLineDatasets
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: {duration: 200},
        interaction: {mode: 'index', intersect: false},
        plugins: {
          legend: {display: true, labels: {
            color: '#334155', font: {size: 10}, boxWidth: 28, pointStyleWidth: 28, padding: 10, usePointStyle: true,
            generateLabels: chart => Chart.defaults.plugins.legend.labels.generateLabels(chart).map(item => {
              const dataset = chart.data.datasets[item.datasetIndex] || {};
              return {
                ...item,
                pointStyle: 'line',
                lineDash: dataset.borderDash || [],
                lineWidth: dataset.borderWidth || 1,
                strokeStyle: dataset.borderColor,
                fillStyle: dataset.borderColor
              };
            }),
            sort: (a, b) => (legendOrder.get(legendKey(a.text)) ?? 999) - (legendOrder.get(legendKey(b.text)) ?? 999)
          }},
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
