const DATA_VERSION = 'data-20260827-0700';
const CHART_TRADING_DAYS = 120;
const GRID = '#e2e8f0';
const TICK = '#64748b';
const COLOR = {
  positive: '#16a34a',
  negative: '#dc2626',
  muted: '#64748b',
  blue: '#2563eb'
};
const ALIGNMENT_1_5_20_60_120 = 'alignment_1_5_20_60_120';
const ALIGNMENT_5_20_60_120 = 'alignment_5_20_60_120';
const ALIGNMENT_20_60_120 = 'alignment_20_60_120';
const VWAP20_DIRECTION = 'vwap20_direction';
const ALIGNMENT_OPTIONS = [
  { key: ALIGNMENT_1_5_20_60_120, label: '1>5>20>60>120', fallbackLabel: '1 > 5 > 20 > 60 > 120', horizon: '단기', tone: 'short' },
  { key: ALIGNMENT_5_20_60_120, label: '5>20>60>120', fallbackLabel: '5 > 20 > 60 > 120', horizon: '중기', tone: 'medium' },
  { key: ALIGNMENT_20_60_120, label: '20>60>120', fallbackLabel: '20 > 60 > 120', horizon: '장기', tone: 'long' }
];
const DIRECTION_OPTION = { key: VWAP20_DIRECTION, label: '20일 방향', fallbackLabel: 'VWAP20 방향', horizon: '방향', tone: 'direction' };
const CHART_STRATEGY_OPTIONS = [...ALIGNMENT_OPTIONS, DIRECTION_OPTION];
const DEFAULT_ALIGNMENT_STRATEGY = ALIGNMENT_1_5_20_60_120;
const ALIGNMENT_ENTRY_RULE = '첫 평가 정배열은 초기 진입 · 이후 전환 확인 → 다음 거래일 1d VWAP 체결';
const DIRECTION_ENTRY_RULE = 'VWAP20 전일 대비 상승 시 보유 · 방향 전환 확인 → 다음 거래일 실제 시초가 체결';
const DEFAULT_SORT = { key: 'alignment_1_5_20_60_120_return_pct', dir: 'desc' };
const VP_PERIODS = ['1d', '5d', '20d', '60d', '120d'];
const PRICE_LINE_DEFS = [
  { label: '1d', window: 1, color: '#eab308', dash: [], width: 1.15 },
  { label: '5d', window: 5, color: '#dc2626', dash: [], width: 1.15 },
  { label: '20d', window: 20, color: '#16a34a', dash: [], width: 1.15 },
  { label: '60d', window: 60, color: '#2563eb', dash: [], width: 1.15 },
  { label: '120d', window: 120, color: '#000000', dash: [], width: 1.15 }
];
const PRICE_DATASET_ORDER = ['BUY', 'SELL', ...PRICE_LINE_DEFS.map(def => def.label)];

const ALIGNMENT_SIGNAL_COLUMNS = ALIGNMENT_OPTIONS.map((option, index) => ({
  key: `signal_${index + 1}`,
  label: `신호 ${index + 1}`,
  type: 'text',
  get: row => row.strategy.strategies?.[option.key]?.latest?.signal
}));
const ALIGNMENT_RETURN_COLUMNS = ALIGNMENT_OPTIONS.map(option => ({
  key: `${option.key}_return_pct`,
  label: `${option.label} 수익률`,
  type: 'number',
  get: row => row.strategy.backtest?.rolling_120d?.[`${option.key}_return_pct`]
}));
const MOMENTUM_COLUMNS = [
  { key: 'name', label: '종목', type: 'text', get: row => row.name },
  ...ALIGNMENT_SIGNAL_COLUMNS,
  ...ALIGNMENT_RETURN_COLUMNS,
  { key: 'buy_hold_return_pct', label: '120일 수익률', type: 'number', get: row => row.strategy.backtest?.rolling_120d?.buy_hold_return_pct }
];
const SORT_FIELDS = Object.fromEntries(MOMENTUM_COLUMNS.map(column => [column.key, column.get]));
const NUMERIC_SORT_FIELDS = new Set(MOMENTUM_COLUMNS.filter(column => column.type === 'number').map(column => column.key));

let priceChart = null;
let vpChart = null;
let currentVpPeriod = '1d';
let currentAlignmentStrategy = DEFAULT_ALIGNMENT_STRATEGY;
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
    const getter = SORT_FIELDS[sortState.key] || SORT_FIELDS.alignment_1_5_20_60_120_return_pct;
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
      const latestShort = strategy?.strategies?.[ALIGNMENT_1_5_20_60_120]?.latest || {};
      const latestMedium = strategy?.strategies?.[ALIGNMENT_5_20_60_120]?.latest || {};
      const latestLong = strategy?.strategies?.[ALIGNMENT_20_60_120]?.latest || {};
      const rolling120 = strategy?.backtest?.rolling_120d || {};
      const tr = document.createElement('tr');
      tr.className = 'momentum-row' + (name === currentDetailName ? ' detail-active' : '');
      tr.append(
        createCell(name),
        createSignalCell(latestShort.signal),
        createSignalCell(latestMedium.signal),
        createSignalCell(latestLong.signal),
        createCell(fmtPct(rolling120.alignment_1_5_20_60_120_return_pct), { color: statColor(rolling120.alignment_1_5_20_60_120_return_pct), weight: '800' }),
        createCell(fmtPct(rolling120.alignment_5_20_60_120_return_pct), { color: statColor(rolling120.alignment_5_20_60_120_return_pct), weight: '800' }),
        createCell(fmtPct(rolling120.alignment_20_60_120_return_pct), { color: statColor(rolling120.alignment_20_60_120_return_pct), weight: '800' }),
        createCell(fmtPct(rolling120.buy_hold_return_pct), { color: statColor(rolling120.buy_hold_return_pct), weight: '800' })
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
        initAlignmentTabs();
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
      initAlignmentTabs();
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

  function fmtJournalDate(value) {
    return value ? String(value).replaceAll('-', '.') : '–';
  }

  function fmtJournalPrice(value) {
    return value == null ? '–' : Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 0 });
  }

  function fmtWinRate(value) {
    return value == null ? '–' : `${Number(value).toFixed(2)}%`;
  }

  function createJournalMetric(label, value, color=null) {
    const metric = document.createElement('div');
    metric.className = 'journal-metric';
    const metricLabel = document.createElement('span');
    metricLabel.textContent = label;
    const metricValue = document.createElement('strong');
    metricValue.textContent = value;
    if (color) metricValue.style.color = color;
    metric.append(metricLabel, metricValue);
    return metric;
  }

  function createJournalTable(records) {
    const wrap = document.createElement('div');
    wrap.className = 'journal-table-wrap';
    if (!records.length) {
      const empty = document.createElement('div');
      empty.className = 'journal-empty';
      empty.textContent = '해당 기간에 체결된 거래가 없습니다.';
      wrap.appendChild(empty);
      return wrap;
    }

    const table = document.createElement('table');
    table.className = 'journal-table';
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['진입일', '진입가', '청산일', '청산가', '수익률'].forEach(label => {
      const th = document.createElement('th');
      th.textContent = label;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    const tbody = document.createElement('tbody');
    [...records].reverse().forEach(record => {
      const isOpen = record.status === 'OPEN';
      const tr = document.createElement('tr');
      tr.className = isOpen ? 'journal-open-row' : '';
      const entryLabel = record.initial_entry
        ? `초기 · ${fmtJournalDate(record.entry_date)}`
        : fmtJournalDate(record.entry_date);
      const values = [
        entryLabel,
        fmtJournalPrice(record.entry_price),
        isOpen ? '보유 중' : fmtJournalDate(record.exit_date),
        isOpen ? `${fmtJournalPrice(record.valuation_price)}*` : fmtJournalPrice(record.exit_price),
        fmtPct(record.return_pct),
      ];
      values.forEach((value, index) => {
        const td = document.createElement('td');
        td.textContent = value;
        if (index === 0 && record.initial_entry) td.className = 'journal-initial-label';
        if (index === 2 && isOpen) td.className = 'journal-open-label';
        if (index === 4) {
          td.classList.add('journal-return');
          td.style.color = statColor(record.return_pct);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.append(thead, tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function createJournalCard({tone, horizon, title, rule, metrics, records, note}) {
    const card = document.createElement('article');
    card.className = `journal-card journal-card-${tone}`;

    const header = document.createElement('div');
    header.className = 'journal-card-head';
    const titleWrap = document.createElement('div');
    const badge = document.createElement('span');
    badge.className = 'journal-horizon-badge';
    badge.textContent = horizon;
    const heading = document.createElement('h4');
    heading.textContent = title;
    titleWrap.append(badge, heading);
    const count = document.createElement('span');
    count.className = 'journal-count';
    count.textContent = `${records.length}개 기록 · 최신순`;
    header.append(titleWrap, count);

    const ruleText = document.createElement('p');
    ruleText.className = 'journal-rule';
    ruleText.textContent = rule;

    const summary = document.createElement('div');
    summary.className = 'journal-summary';
    metrics.forEach(metric => summary.appendChild(createJournalMetric(metric.label, metric.value, metric.color)));

    const footnote = document.createElement('p');
    footnote.className = 'journal-note';
    footnote.textContent = note;

    card.append(header, ruleText, summary, createJournalTable(records), footnote);
    return card;
  }

  function createHorizonItem(horizon, label, value, tone) {
    const item = document.createElement('div');
    item.className = `journal-horizon-item journal-horizon-${tone}`;
    const badge = document.createElement('span');
    badge.textContent = horizon;
    const name = document.createElement('strong');
    name.textContent = label;
    const result = document.createElement('em');
    result.textContent = fmtPct(value);
    result.style.color = statColor(value);
    item.append(badge, name, result);
    return item;
  }

  function createAlignmentJournalCard({ option, label, backtest, records }, costNote) {
    return createJournalCard({
      tone: option.tone,
      horizon: option.horizon,
      title: `정배열 ${label}`,
      rule: ALIGNMENT_ENTRY_RULE,
      metrics: [
        {label: '누적 수익률', value: fmtPct(backtest.return_pct), color: statColor(backtest.return_pct)},
        {label: '완료 거래', value: `${backtest.trades ?? 0}건`},
        {label: '승률', value: fmtWinRate(backtest.win_rate_pct)},
      ],
      records,
      note: `${label} · ${costNote} · *보유 중은 최신 1d VWAP 평가`,
    });
  }

  function createDirectionJournalCard({ backtest, buyHoldReturn, latest, records }, costNote) {
    return createJournalCard({
      tone: DIRECTION_OPTION.tone,
      horizon: DIRECTION_OPTION.horizon,
      title: 'VWAP20 방향 전략',
      rule: DIRECTION_ENTRY_RULE,
      metrics: [
        {label: '120일 전략수익률', value: fmtPct(backtest.return_pct), color: statColor(backtest.return_pct)},
        {label: '단순 보유', value: fmtPct(buyHoldReturn), color: statColor(buyHoldReturn)},
        {label: 'MDD', value: fmtPct(backtest.mdd_pct), color: statColor(backtest.mdd_pct)},
        {label: '완료 거래', value: `${backtest.trades ?? 0}건`},
        {label: '승률', value: fmtWinRate(backtest.win_rate_pct)},
        {label: '현재 상태', value: latest.status_text || '–'},
      ],
      records,
      note: `VWAP20 전일 대비 방향 · ${costNote} · 다음 거래일 실제 시초가 · *보유 중은 최신 종가 평가`,
    });
  }

  function renderBacktestJournals(detailData) {
    const section = document.getElementById('backtest-journal-section');
    if (!section) return;
    section.replaceChildren();

    const strategy = detailData.strategy_signal || {};
    const journals = detailData.backtest_journals || {};
    const alignmentContexts = ALIGNMENT_OPTIONS.map(option => {
      const payload = strategy.strategies?.[option.key] || {};
      return {
        option,
        label: payload.label || option.fallbackLabel,
        backtest: payload.backtest || {},
        records: journals[option.key] || [],
      };
    });
    const directionPayload = strategy.strategies?.[VWAP20_DIRECTION] || {};
    const directionContext = {
      option: DIRECTION_OPTION,
      label: directionPayload.label || DIRECTION_OPTION.fallbackLabel,
      backtest: directionPayload.backtest || {},
      latest: directionPayload.latest || {},
      buyHoldReturn: strategy.backtest?.rolling_120d?.buy_hold_return_pct,
      records: journals[VWAP20_DIRECTION] || [],
    };

    const costModel = strategy.cost_model || {};
    const accountLabel = costModel.account_label || '추천계좌';
    const transactionTax = Number(costModel.transaction_tax_sell_pct || 0);
    const transactionTaxNote = transactionTax > 0
      ? `매도 거래세 ${transactionTax.toFixed(2)}%`
      : '거래별 소득세 없음';
    const costNote = `${accountLabel} · 편도 수수료 0.03% · ${transactionTaxNote}`;

    const sectionHead = document.createElement('div');
    sectionHead.className = 'journal-section-head';
    const copy = document.createElement('div');
    const eyebrow = document.createElement('div');
    eyebrow.className = 'journal-eyebrow';
    eyebrow.textContent = 'STRATEGY REVIEW';
    const title = document.createElement('h3');
    title.textContent = '전략 백테스트 일지';
    const description = document.createElement('p');
    description.textContent = '최근 120거래일의 정배열 3종과 VWAP20 방향 매매 기록을 비교합니다.';
    copy.append(eyebrow, title, description);
    const period = document.createElement('span');
    period.className = 'journal-period';
    period.textContent = '최근 120 거래일';
    sectionHead.append(copy, period);

    const horizons = document.createElement('div');
    horizons.className = 'journal-horizon-strip';
    horizons.append(
      ...alignmentContexts.map(({ option, label, backtest }) => (
        createHorizonItem(option.horizon, label, backtest.return_pct, option.tone)
      )),
      createHorizonItem(
        directionContext.option.horizon,
        directionContext.label,
        directionContext.backtest.return_pct,
        directionContext.option.tone,
      ),
    );

    const grid = document.createElement('div');
    grid.className = 'journal-grid';
    grid.append(
      ...alignmentContexts.map(context => createAlignmentJournalCard(context, costNote)),
      createDirectionJournalCard(directionContext, costNote),
    );

    section.append(sectionHead, horizons, grid);
  }

  function renderDetailPanels() {
    const pricePanel = createChartPanel('', 'chart-price');
    const alignmentTabs = document.createElement('div');
    alignmentTabs.className = 'alignment-tabs';
    alignmentTabs.id = 'alignment-tabs';
    alignmentTabs.setAttribute('role', 'tablist');
    alignmentTabs.setAttribute('aria-label', '차트 전략 선택');
    CHART_STRATEGY_OPTIONS.forEach(option => {
      const button = document.createElement('button');
      const active = option.key === currentAlignmentStrategy;
      button.className = 'alignment-tab' + (active ? ' active' : '');
      button.dataset.strategy = option.key;
      button.textContent = option.label;
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', String(active));
      alignmentTabs.appendChild(button);
    });
    pricePanel.insertBefore(alignmentTabs, pricePanel.querySelector('.chart-wrap'));
    const directionStatus = document.createElement('div');
    directionStatus.className = 'direction-status';
    directionStatus.id = 'direction-status';
    directionStatus.hidden = true;
    pricePanel.insertBefore(directionStatus, pricePanel.querySelector('.chart-wrap'));
    const vpPanel = createChartPanel('Volume Profile', 'chart-vp');
    vpPanel.classList.add('volume-profile-panel');
    const journalSection = document.createElement('section');
    journalSection.className = 'backtest-journal-section';
    journalSection.id = 'backtest-journal-section';

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
    view.detailContent.replaceChildren(pricePanel, vpPanel, journalSection);
  }

  function initAlignmentTabs() {
    const tabs = document.getElementById('alignment-tabs');
    if (!tabs) return;
    tabs.addEventListener('click', event => {
      if (!event.target.matches('.alignment-tab')) return;
      const strategyKey = event.target.dataset.strategy;
      if (!CHART_STRATEGY_OPTIONS.some(option => option.key === strategyKey)) return;
      currentAlignmentStrategy = strategyKey;
      document.querySelectorAll('.alignment-tab').forEach(button => {
        const active = button.dataset.strategy === currentAlignmentStrategy;
        button.classList.toggle('active', active);
        button.setAttribute('aria-selected', String(active));
      });
      const ticker = data[currentDetailName]?.ticker;
      if (!ticker || !detailCache[ticker]) return;
      renderPriceChart(detailCache[ticker]);
    });
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
    renderBacktestJournals(detailData);
    view.detailSection.scrollIntoView({behavior:'smooth', block:'start'});
  }

  // ─── Panel A: Price + VWAP ─────────────────────────────
  function renderDirectionStatus(detailData) {
    const status = document.getElementById('direction-status');
    if (!status) return;
    const isDirection = currentAlignmentStrategy === VWAP20_DIRECTION;
    status.hidden = !isDirection;
    if (!isDirection) return;

    const latest = detailData.strategy_signal?.strategies?.[VWAP20_DIRECTION]?.latest || {};
    const signalTone = latest.signal === 'BUY' ? 'up' : latest.signal === 'SELL' ? 'down' : 'wait';
    status.className = `direction-status direction-status-${signalTone}`;
    status.replaceChildren();
    [
      ['VWAP20', fmtPct(latest.direction_change_pct)],
      ['방향', latest.direction || '대기'],
      ['현재', latest.position || '현금'],
      ['다음 시초가', latest.next_open_action || '대기'],
    ].forEach(([label, value]) => {
      const item = document.createElement('span');
      const key = document.createElement('small');
      const result = document.createElement('strong');
      key.textContent = label;
      result.textContent = value;
      item.append(key, result);
      status.appendChild(item);
    });
    const summary = document.createElement('em');
    summary.textContent = latest.status_text || '방향 미산출 · 대기';
    status.appendChild(summary);
  }

  function renderPriceChart(detailData) {
    renderDirectionStatus(detailData);
    const ohlcv = detailData.ohlcv.slice(-CHART_TRADING_DAYS);
    const labels = ohlcv.map(d => d.date);
    const selectedSignals = detailData.strategy_signal?.strategies?.[currentAlignmentStrategy]?.signals || [];
    const signalMap = new Map(selectedSignals.map(signal => [signal.date, signal]));
    const markerData = type => labels.map((date, i) => {
      const signal = signalMap.get(date);
      if (signal?.type !== type) return null;
      return signal.marker_price ?? ohlcv[i]?.vwap_5d ?? null;
    });
    const lineData = def => ohlcv.map(d => d[`vwap_${def.window}d`] ?? null);
    const directionMode = currentAlignmentStrategy === VWAP20_DIRECTION;
    const vwapLineDatasets = PRICE_LINE_DEFS.map((def, idx) => ({
      label: def.label,
      data: lineData(def),
      borderColor: def.color,
      borderWidth: directionMode && def.window === 20 ? 2.6 : def.width,
      borderDash: def.dash,
      segment: directionMode && def.window === 20 ? {
        borderColor: ctx => {
          const previous = ctx.p0.parsed.y;
          const current = ctx.p1.parsed.y;
          if (previous == null || current == null) return def.color;
          return current > previous ? COLOR.positive : COLOR.negative;
        },
      } : undefined,
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
          tooltip: {callbacks: {label: ctx => {
            const signal = signalMap.get(labels[ctx.dataIndex]);
            const label = ctx.dataset.label === 'BUY' && signal?.initial_entry ? 'INITIAL BUY' : ctx.dataset.label;
            return ` ${label}: ${ctx.parsed.y?.toLocaleString(undefined, {maximumFractionDigits: 2})}`;
          }}}
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
