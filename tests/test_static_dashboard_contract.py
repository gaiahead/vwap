import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_DATA_VERSION = "data-20260830-price-chart-120d-selection"


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_monitor_has_exact_live_signal_columns_and_name_sort():
    html = read("index.html")
    app = read("app.js")
    headers = re.findall(r'<th data-sort="[^"]+">([^<]+)</th>', html)
    sort_keys = re.findall(r'<th data-sort="([^"]+)">', html)

    assert headers == ["종목", "신호 1", "신호 2", "신호 3"]
    assert sort_keys == ["name", "signal_1", "signal_2", "signal_3"]
    assert "const DEFAULT_SORT = { key: 'name', dir: 'asc' };" in app
    assert "const ALIGNMENT_SIGNAL_COLUMNS = ALIGNMENT_OPTIONS.map" in app
    assert "strategies?.[option.key]?.latest?.signal" in app
    assert "key: `signal_${index + 1}`" in app
    assert "label: `신호 ${index + 1}`" in app

    combined = html + app
    for token in [
        "수익률",
        "return_pct",
        "buy_hold",
        "ALIGNMENT_RETURN_COLUMNS",
        "NUMERIC_SORT_FIELDS",
        "rolling_120d",
    ]:
        assert token not in combined


def test_monitor_keeps_three_strict_live_alignment_definitions():
    html = read("index.html")
    app = read("app.js")

    assert "신호 1은 1d &gt; 5d &gt; 20d &gt; 60d &gt; 120d" in html
    assert "신호 2는 5d &gt; 20d &gt; 60d &gt; 120d" in html
    assert "신호 3은 20d &gt; 60d &gt; 120d" in html
    assert "평가 첫날" not in html
    assert "다음 거래일" not in html
    assert "const ALIGNMENT_1_5_20_60_120 = 'alignment_1_5_20_60_120';" in app
    assert "const ALIGNMENT_5_20_60_120 = 'alignment_5_20_60_120';" in app
    assert "const ALIGNMENT_20_60_120 = 'alignment_20_60_120';" in app
    assert "row-indicator" not in app + read("style.css")
    assert "signal-cell buy" in app
    assert "signal-cell sell" in app


def test_frontend_removes_backtest_journal_and_strategy_chart_runtime():
    combined = read("app.js") + read("index.html") + read("style.css")
    lowered = combined.replace(NEW_DATA_VERSION, "").lower()

    for token in [
        "backtest",
        "journal",
        "vwap20_direction",
        "chart_strategy",
        "alignment-tabs",
        "alignment-tab",
        "direction-status",
        "cost_model",
        "win_rate",
        "mdd_pct",
    ]:
        assert token not in lowered


def test_price_chart_is_fixed_to_latest_120_rows_without_range_controls():
    app = read("app.js")
    combined = app + read("index.html") + read("style.css")

    assert "const PRICE_CHART_TRADING_DAYS = 120;" in app
    assert "const ohlcv = detailData.ohlcv.slice(-PRICE_CHART_TRADING_DAYS);" in app
    assert "currentChartTradingDays" not in app
    assert "CHART_TRADING_DAY_OPTIONS" not in app
    for token in [
        "chart-range-control",
        "chart-range-label",
        "chart-range-options",
        "chart-range-button",
        "차트 범위",
        "120일",
    ]:
        assert token not in combined


def test_price_chart_has_exact_five_vwap_datasets_and_keeps_240d_volume_profile():
    app = read("app.js")
    definitions = re.findall(
        r"label: '([^']+)', window: (\d+), color: '(#[0-9a-f]+)'",
        app,
    )

    assert definitions == [
        ("1d", "1", "#eab308"),
        ("5d", "5", "#dc2626"),
        ("20d", "20", "#16a34a"),
        ("60d", "60", "#2563eb"),
        ("120d", "120", "#7c3aed"),
    ]
    assert "datasets: vwapLineDatasets" in app
    assert "const PRICE_DATASET_ORDER = PRICE_LINE_DEFS.map(def => def.label);" in app
    assert "const VP_PERIODS = ['1d', '5d', '20d', '60d', '120d', '240d'];" in app
    assert "Volume Profile" in app
    assert "vwap_240d" not in app

    for token in [
        "label: 'BUY'",
        "label: 'SELL'",
        "signalDatasets",
        "selectedSignals",
        "signalMap",
        "markerData",
        "marker_price",
        "pointStyle: 'triangle'",
        "pointRotation",
        "INITIAL BUY",
    ]:
        assert token not in app


def test_chart_visual_trend_helpers_preserve_colors_and_slope_opacity_with_uniform_width():
    app = read("app.js")
    for token in [
        "function classifyVwapSegmentState(values, startIndex, endIndex)",
        "function getVwapTrendStyle",
        "Object.defineProperty(window, 'VWAP_CHART_TEST_API'",
    ]:
        assert token in app

    assert re.search(
        r"classifyVwapSegmentState\(\s*values,\s*context\.p0DataIndex,\s*context\.p1DataIndex\s*\)",
        app,
    )
    for obsolete_token in [
        "VWAP_TREND_LOOKBACK",
        "VWAP_TREND_DEADBAND_PCT",
        "VWAP_TREND_CONFIRMATION_SEGMENTS",
        "classifyVwapTrendCandidate",
        "classifyVwapTrendStates",
        "trendLookback",
        "deadbandPct",
        "confirmationSegments",
        "pendingState",
        "pendingCount",
    ]:
        assert obsolete_token not in app

    assert "current > previous ? COLOR.positive : COLOR.negative" not in app
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const shortOscillation = [100, 100.0001, 100, 100.0002];
const alternating = [
  api.classifyVwapSegmentState(shortOscillation, 0, 1),
  api.classifyVwapSegmentState(shortOscillation, 1, 2),
  api.classifyVwapSegmentState(shortOscillation, 2, 3),
];
const edgeCases = {
  equal: api.classifyVwapSegmentState([100, 100], 0, 1),
  missingStart: api.classifyVwapSegmentState([null, 100], 0, 1),
  missingEnd: api.classifyVwapSegmentState([100], 0, 1),
  nonFiniteStart: api.classifyVwapSegmentState([NaN, 100], 0, 1),
  nonFiniteEnd: api.classifyVwapSegmentState([100, Infinity], 0, 1),
};
const periods = [1, 5, 20, 60, 120];
const colors = Object.fromEntries(periods.map(period => [period, {
  rising: api.getVwapTrendStyle(period, 'rising').baseColor,
  flat: api.getVwapTrendStyle(period, 'flat').baseColor,
  falling: api.getVwapTrendStyle(period, 'falling').baseColor,
}]));
const states = ['rising', 'flat', 'falling'];
const widths = periods.flatMap(period => states.map(
  state => api.getVwapTrendStyle(period, state).borderWidth
));
const opacities = Object.fromEntries(states.map(
  state => [state, api.getVwapTrendStyle(20, state).opacity]
));
console.log(JSON.stringify({
  alternating,
  edgeCases,
  colors,
  widths,
  opacities,
  missing240dStyle: api.getVwapTrendStyle(240, 'flat')
}));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["alternating"] == ["rising", "falling", "rising"]
    assert set(result["edgeCases"].values()) == {"flat"}
    assert set(result["widths"]) == {3}
    assert result["opacities"] == {"rising": 1, "flat": 0.9, "falling": 0.522}
    for states in result["colors"].values():
        assert len(set(states.values())) == 1
    assert result["colors"]["120"]["flat"] == "#7c3aed"
    assert result["missing240dStyle"] is None


def test_volume_profile_tabs_and_panel_survive():
    app = read("app.js")

    assert "let currentVpPeriod = '1d';" in app
    assert "currentVpPeriod = '1d';" in app
    assert "button.className = 'vp-tab'" in app
    assert "renderVpChart(detailData, currentVpPeriod);" in app
    assert "view.detailContent.replaceChildren(pricePanel, vpPanel);" in app


def test_volume_profile_keeps_only_rounded_vwap_annotation():
    app = read("app.js")
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const detailData = { ohlcv: [{close: 1}, {close: 257000}] };
const vp = {
  vwap: 259666.6667,
  buckets: [{price: 257250}, {price: 259750}]
};
const annotations = api.buildVpAnnotations(detailData, vp);
console.log(JSON.stringify(annotations));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    annotations = json.loads(completed.stdout)

    assert set(annotations) == {"vwapLine"}
    assert annotations["vwapLine"]["value"] == 1
    assert annotations["vwapLine"]["label"]["content"] == "VWAP 259,667"
    assert annotations["vwapLine"]["label"]["position"] == "end"
    assert "const labels = buckets.map(bucket => formatPrice(bucket.price));" in app
    assert "latestCloseLine" not in app
    assert "최근 종가" not in app


def test_korean_integer_price_formatting_rounds_decimals_and_handles_null_safely():
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const formatPrice = context.window.VWAP_CHART_TEST_API.formatPrice;
console.log(JSON.stringify([
  formatPrice(123456.5),
  formatPrice('9876.4'),
  formatPrice(null),
  formatPrice(undefined),
  formatPrice('not-a-price')
]));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == ["123,457", "9,876", "–", "–", "–"]


def test_price_chart_config_formats_y_axis_and_tooltip_prices_as_integers():
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const ohlcv = Array.from({length: 125}, (_, index) => ({
  date: 'day-' + index,
  vwap_1d: index === 124 ? 123456.5 : index
}));
const config = api.buildPriceChartConfig({ohlcv});
console.log(JSON.stringify({
  rowCount: config.data.labels.length,
  dateBounds: [config.data.labels[0], config.data.labels.at(-1)],
  datasetLabels: config.data.datasets.map(dataset => dataset.label),
  yTick: config.options.scales.y.ticks.callback(123456.5),
  tooltip: config.options.plugins.tooltip.callbacks.label({
    dataset: {label: '1d'},
    parsed: {y: 123456.5}
  }),
  rawValue: config.data.datasets[0].data.at(-1),
  hasPriceAnnotationOptions: Object.hasOwn(config.options.plugins, 'annotation')
}));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "rowCount": 120,
        "dateBounds": ["day-5", "day-124"],
        "datasetLabels": ["1d", "5d", "20d", "60d", "120d"],
        "yTick": "123,457",
        "tooltip": "1d: 123,457",
        "rawValue": 123456.5,
        "hasPriceAnnotationOptions": False,
    }


def test_date_selection_stores_valid_index_and_date_on_chart_and_rejects_invalid_input():
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const build = api.buildPriceChartDateSelection;
const labels = ['2026-08-27', '2026-08-28'];
const config = api.buildPriceChartConfig({ohlcv: labels.map(date => ({date}))});
const chart = {
  data: config.data
};
const selected = api.selectPriceChartIndex(chart, 1);
const sameSelection = api.selectPriceChartIndex(chart, 1);
const invalidSelection = api.selectPriceChartIndex(chart, 9);
console.log(JSON.stringify({
  valid: build(labels, 1),
  negative: build(labels, -1),
  outOfRange: build(labels, 2),
  fractional: build(labels, 0.5),
  missingLabels: build(null, 0),
  selected,
  sameSelection,
  invalidSelection,
  persistedSelection: chart.$priceChartDateSelection,
  hasPriceAnnotationOptions: Object.hasOwn(config.options.plugins, 'annotation')
}));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["valid"] == {"index": 1, "date": "2026-08-28"}
    assert result["negative"] is None
    assert result["outOfRange"] is None
    assert result["fractional"] is None
    assert result["missingLabels"] is None
    assert result["selected"] is True
    assert result["sameSelection"] is False
    assert result["invalidSelection"] is False
    assert result["persistedSelection"] == {"index": 1, "date": "2026-08-28"}
    assert result["hasPriceAnnotationOptions"] is False


def test_nearest_price_chart_index_uses_chart_area_math_and_accepts_edge_hit_area():
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const nearest = context.window.VWAP_CHART_TEST_API.nearestPriceChartIndex;
const labels = ['first', 'second', 'third', 'last'];
let scaleLookupCount = 0;
let elementLookupCount = 0;
const chart = {
  data: {labels},
  chartArea: {left: 10, right: 310, top: 20, bottom: 220},
  scales: {x: {getValueForPixel: () => {
    scaleLookupCount += 1;
    throw new Error('selection must not depend on the category scale');
  }}},
  getElementsAtEventForMode: () => {
    elementLookupCount += 1;
    throw new Error('selection must not depend on element lookup');
  }
};

const result = {
  exactFirst: nearest(chart, {x: 10, y: 100}),
  exactLast: nearest(chart, {x: 310, y: 100}),
  interiorRounded: nearest(chart, {x: 160, y: 100}),
  leftEdgeClamped: nearest(chart, {x: -2, y: 20}),
  rightEdgeClamped: nearest(chart, {x: 322, y: 220}),
  tooFarLeft: nearest(chart, {x: -3, y: 100}),
  tooFarRight: nearest(chart, {x: 323, y: 100}),
  abovePlot: nearest(chart, {x: 10, y: 19}),
  belowPlot: nearest(chart, {x: 310, y: 221}),
  missingY: nearest(chart, {x: 160}),
  missingLabels: nearest({chartArea: chart.chartArea}, {x: 10, y: 100}),
  oneLabel: nearest({
    data: {labels: ['only']},
    chartArea: chart.chartArea
  }, {x: 322, y: 100}),
  scaleLookupCount,
  elementLookupCount
};
console.log(JSON.stringify(result));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "exactFirst": 0,
        "exactLast": 3,
        "interiorRounded": 2,
        "leftEdgeClamped": 0,
        "rightEdgeClamped": 3,
        "tooFarLeft": -1,
        "tooFarRight": -1,
        "abovePlot": -1,
        "belowPlot": -1,
        "missingY": -1,
        "missingLabels": -1,
        "oneLabel": 0,
        "scaleLookupCount": 0,
        "elementLookupCount": 0,
    }


def test_price_chart_local_plugin_draws_finite_circles_and_inset_endpoint_lines():
    app = read("app.js")
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const config = api.buildPriceChartConfig({
  ohlcv: [
    {
      date: 'first',
      vwap_1d: 11,
      vwap_5d: 21,
      vwap_20d: 31,
      vwap_60d: 41,
      vwap_120d: 51
    },
    {
      date: 'second',
      vwap_1d: 12,
      vwap_5d: null,
      vwap_20d: '',
      vwap_60d: NaN,
      vwap_120d: Infinity
    },
    {
      date: 'third',
      vwap_1d: 13,
      vwap_5d: 23,
      vwap_20d: 33,
      vwap_60d: 43,
      vwap_120d: 53
    },
    {
      date: 'last',
      vwap_1d: 14,
      vwap_5d: 24,
      vwap_20d: 34,
      vwap_60d: 44,
      vwap_120d: 54
    }
  ]
});
const plugin = config.plugins.find(candidate => candidate.id === 'priceChartDateSelection');
const frames = [];
const contextCalls = {save: 0, restore: 0, fillText: 0, fillRect: 0};
let activeFrame = null;
let path = null;
let hiddenDatasetIndex = -1;
let updateCount = 0;
let xScaleLookupCount = 0;
const ctx = {
  save() { contextCalls.save += 1; },
  restore() { contextCalls.restore += 1; },
  setLineDash(dash) { this.dash = [...dash]; },
  beginPath() { path = {}; },
  moveTo(x, y) { path.from = [x, y]; },
  lineTo(x, y) { path.to = [x, y]; },
  stroke() {
    activeFrame.line = {
      x: path.from[0],
      top: path.from[1],
      bottom: path.to[1],
      strokeStyle: this.strokeStyle,
      lineWidth: this.lineWidth,
      dash: this.dash
    };
  },
  arc(x, y, radius, startAngle, endAngle) {
    path.circle = {x, y, radius, startAngle, endAngle};
  },
  fill() {
    activeFrame.circles.push({...path.circle, color: this.fillStyle});
  },
  fillText() { contextCalls.fillText += 1; },
  fillRect() { contextCalls.fillRect += 1; }
};
const chart = {
  data: config.data,
  options: config.options,
  chartArea: {left: 10, right: 310, top: 20, bottom: 220},
  ctx,
  scales: {
    x: {
      getPixelForValue: () => {
        xScaleLookupCount += 1;
        throw new Error('selection x must come from chart-area math');
      }
    },
    y: {getPixelForValue: value => 210 - Number(value)}
  },
  isDatasetVisible: datasetIndex => datasetIndex !== hiddenDatasetIndex,
  getElementsAtEventForMode: () => {
    throw new Error('the local plugin must not use element lookup');
  },
  update: () => { updateCount += 1; }
};

function dispatch(type, x, y, inChartArea = false) {
  const args = {event: {type, x, y}, inChartArea, changed: false};
  plugin.afterEvent(chart, args);
  return {
    changed: args.changed,
    selection: chart.$priceChartDateSelection
      ? {...chart.$priceChartDateSelection}
      : null
  };
}

function drawFrame() {
  activeFrame = {line: null, circles: []};
  plugin.afterDatasetsDraw(chart);
  frames.push(activeFrame);
  return activeFrame;
}

const emptyFrame = drawFrame();
const first = dispatch('mousemove', -2, 100);
const firstFrame = drawFrame();
const sameFirst = dispatch('mousemove', 0, 100);
const finiteOnlyDate = dispatch('click', 110, 100);
const finiteOnlyFrame = drawFrame();
const mouseRelease = dispatch('mouseup', 210, 100);
const pointerRelease = dispatch('pointerup', 210, 100);
hiddenDatasetIndex = 2;
const interiorTouch = dispatch('touchstart', 210, 100);
const hiddenDatasetFrame = drawFrame();
hiddenDatasetIndex = -1;
const last = dispatch('touchmove', 322, 100);
const lastFrame = drawFrame();
const abovePlot = dispatch('mousemove', 10, 19);
const beyondEdgeArea = dispatch('mousemove', -3, 100);
const unrelated = dispatch('mouseout', 110, 100);

const drawnFrames = [firstFrame, finiteOnlyFrame, hiddenDatasetFrame, lastFrame];
const datasetColors = config.data.datasets.map(dataset => dataset.borderColor);
const circles = drawnFrames.flatMap(frame => frame.circles);
console.log(JSON.stringify({
  pluginIds: config.plugins.map(candidate => candidate.id),
  hasDrawHook: typeof plugin.afterDatasetsDraw === 'function',
  interaction: config.options.interaction,
  hasTooltip: typeof config.options.plugins.tooltip.callbacks.label === 'function',
  tooltipKeepsDefaultDateTitle: !Object.hasOwn(config.options.plugins.tooltip.callbacks, 'title'),
  hasPriceAnnotationOptions: Object.hasOwn(config.options.plugins, 'annotation'),
  hasOnClick: Object.hasOwn(config.options, 'onClick'),
  drawsWithoutSelection: Number(emptyFrame.line !== null) + emptyFrame.circles.length,
  first,
  sameFirst,
  finiteOnlyDate,
  mouseRelease,
  pointerRelease,
  interiorTouch,
  last,
  abovePlot,
  beyondEdgeArea,
  unrelated,
  lineStyles: drawnFrames.map(frame => frame.line),
  circleCounts: drawnFrames.map(frame => frame.circles.length),
  circleRadii: [...new Set(circles.map(circle => circle.radius))],
  circlesAreComplete: circles.every(circle => (
    circle.startAngle === 0 && circle.endAngle === Math.PI * 2
  )),
  firstMarkerColors: firstFrame.circles.map(circle => circle.color),
  datasetColors,
  finiteOnlyMarkerColor: finiteOnlyFrame.circles[0]?.color,
  hiddenColorWasNotDrawn: !hiddenDatasetFrame.circles.some(
    circle => circle.color === datasetColors[2]
  ),
  everyPointRadiusIsZero: config.data.datasets.every(dataset => dataset.pointRadius === 0),
  endpointXs: [firstFrame.line.x, lastFrame.line.x],
  contextCalls,
  xScaleLookupCount,
  updateCount
}));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["pluginIds"] == ["priceChartDateSelection"]
    assert result["hasDrawHook"] is True
    assert result["interaction"] == {"mode": "index", "axis": "x", "intersect": False}
    assert result["hasTooltip"] is True
    assert result["tooltipKeepsDefaultDateTitle"] is True
    assert result["hasPriceAnnotationOptions"] is False
    assert result["hasOnClick"] is False
    assert result["drawsWithoutSelection"] == 0
    assert result["first"] == {
        "changed": True,
        "selection": {"index": 0, "date": "first"},
    }
    assert result["sameFirst"] == {
        "changed": False,
        "selection": {"index": 0, "date": "first"},
    }
    assert result["finiteOnlyDate"] == {
        "changed": True,
        "selection": {"index": 1, "date": "second"},
    }
    assert result["mouseRelease"] == {
        "changed": False,
        "selection": {"index": 1, "date": "second"},
    }
    assert result["pointerRelease"] == {
        "changed": False,
        "selection": {"index": 1, "date": "second"},
    }
    assert result["interiorTouch"] == {
        "changed": True,
        "selection": {"index": 2, "date": "third"},
    }
    assert result["last"] == {
        "changed": True,
        "selection": {"index": 3, "date": "last"},
    }
    for ignored_event in ["abovePlot", "beyondEdgeArea", "unrelated"]:
        assert result[ignored_event] == {
            "changed": False,
            "selection": {"index": 3, "date": "last"},
        }

    assert result["lineStyles"] == [
        {
            "x": 10.5,
            "top": 20,
            "bottom": 220,
            "strokeStyle": "#000000",
            "lineWidth": 1,
            "dash": [],
        },
        {
            "x": 110,
            "top": 20,
            "bottom": 220,
            "strokeStyle": "#000000",
            "lineWidth": 1,
            "dash": [],
        },
        {
            "x": 210,
            "top": 20,
            "bottom": 220,
            "strokeStyle": "#000000",
            "lineWidth": 1,
            "dash": [],
        },
        {
            "x": 309.5,
            "top": 20,
            "bottom": 220,
            "strokeStyle": "#000000",
            "lineWidth": 1,
            "dash": [],
        },
    ]
    assert result["circleCounts"] == [5, 1, 4, 5]
    assert result["circleRadii"] == [4]
    assert result["circlesAreComplete"] is True
    assert result["firstMarkerColors"] == result["datasetColors"]
    assert result["finiteOnlyMarkerColor"] == result["datasetColors"][0]
    assert result["hiddenColorWasNotDrawn"] is True
    assert result["everyPointRadiusIsZero"] is True
    assert result["endpointXs"] == [10.5, 309.5]
    assert all(10 < x < 310 for x in result["endpointXs"])
    assert result["contextCalls"] == {
        "save": 4,
        "restore": 4,
        "fillText": 0,
        "fillRect": 0,
    }
    assert result["xScaleLookupCount"] == 0
    assert result["updateCount"] == 0

    for obsolete in [
        "PRICE_CHART_POINTER_STATES",
        "priceChartPointerX",
        "attachPriceChartPointerDrag",
        "detachPriceChartPointerDrag",
        "pointerdown",
        "pointermove",
        "pointerup",
        "pointercancel",
        "onClick:",
        "selectedDateLine",
        "buildDateSelectionAnnotation",
        "getValueForPixel",
        "getElementsAtEventForMode",
        "선택 날짜",
        "fillText(",
        "fillRect(",
    ]:
        assert obsolete not in app
    assert "plugins: [dateSelectionPlugin]" in app


def test_cache_bust_version_is_consistent_everywhere():
    html = read("index.html")
    app = read("app.js")
    style_match = re.search(r'style\.css\?v=([^"\']+)', html)
    script_match = re.search(r'app\.js\?v=([^"\']+)', html)
    app_match = re.search(r"const DATA_VERSION = '([^']+)'", app)

    assert style_match is not None
    assert script_match is not None
    assert app_match is not None
    assert style_match.group(1) == script_match.group(1) == app_match.group(1) == NEW_DATA_VERSION
    assert '<link rel="icon" href="data:,"/>' in html


def test_obsolete_dashboard_features_are_not_reintroduced():
    combined = read("app.js") + read("index.html") + read("style.css")
    for token in [
        "calcVMS",
        "renderVMS",
        "vms_matrix",
        "momentum-grid",
        "strategy-card",
        "renderCards",
        "rollingProxyVwap",
        "lifecycle",
        "5/20 괴리율",
        "drawdown",
    ]:
        assert token not in combined
