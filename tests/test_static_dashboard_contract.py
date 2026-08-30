import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_DATA_VERSION = "data-20260830-canvas-date-selection"


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


def test_price_chart_is_fixed_to_latest_240_rows_without_range_controls():
    app = read("app.js")
    combined = app + read("index.html") + read("style.css")

    assert "const PRICE_CHART_TRADING_DAYS = 240;" in app
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


def test_price_chart_has_exact_six_vwap_datasets_and_no_trade_markers():
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
        ("240d", "240", "#000000"),
    ]
    assert "datasets: vwapLineDatasets" in app
    assert "const PRICE_DATASET_ORDER = PRICE_LINE_DEFS.map(def => def.label);" in app
    assert "const VP_PERIODS = ['1d', '5d', '20d', '60d', '120d', '240d'];" in app
    assert "Volume Profile" in app

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
const periods = [1, 5, 20, 60, 120, 240];
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
console.log(JSON.stringify({alternating, edgeCases, colors, widths, opacities}));
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
    assert len(set(result["widths"])) == 1
    assert result["opacities"] == {"rising": 1, "flat": 0.9, "falling": 0.522}
    for states in result["colors"].values():
        assert len(set(states.values())) == 1
    assert result["colors"]["120"]["flat"] == "#7c3aed"
    assert result["colors"]["240"]["flat"] == "#000000"


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
const config = api.buildPriceChartConfig({
  ohlcv: [{date: '2026-08-28', vwap_1d: 123456.5}]
});
console.log(JSON.stringify({
  yTick: config.options.scales.y.ticks.callback(123456.5),
  tooltip: config.options.plugins.tooltip.callbacks.label({
    dataset: {label: '1d'},
    parsed: {y: 123456.5}
  }),
  rawValue: config.data.datasets[0].data[0],
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


def test_nearest_price_chart_index_prefers_coordinates_and_bounds_fallback_results():
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const nearest = context.window.VWAP_CHART_TEST_API.nearestPriceChartIndex;
const labels = ['first', 'second', 'third', 'last'];

function chartWithCoordinate(value, fallbackIndex = 0) {
  let elementLookupCount = 0;
  const chart = {
    data: {labels},
    scales: {x: {getValueForPixel: pixel => {
      if (pixel !== 42) throw new Error('unexpected pixel');
      return value;
    }}},
    getElementsAtEventForMode: () => {
      elementLookupCount += 1;
      return [{index: fallbackIndex}];
    }
  };
  return {chart, elementLookupCount: () => elementLookupCount};
}

const exactFirst = chartWithCoordinate(0, 3);
const exactLast = chartWithCoordinate(3, 0);
const interior = chartWithCoordinate(1.6, 0);
const beforeFirst = chartWithCoordinate(-10, 2);
const afterLast = chartWithCoordinate(10, 1);
const invalidCoordinate = chartWithCoordinate(NaN, 2);

const result = {
  exactFirst: nearest(exactFirst.chart, {x: 42}),
  exactLast: nearest(exactLast.chart, {x: 42}),
  interiorRounded: nearest(interior.chart, {x: 42}),
  beforeFirstClamped: nearest(beforeFirst.chart, {x: 42}),
  afterLastClamped: nearest(afterLast.chart, {x: 42}),
  coordinateElementLookups: [
    exactFirst.elementLookupCount(),
    exactLast.elementLookupCount(),
    interior.elementLookupCount(),
    beforeFirst.elementLookupCount(),
    afterLast.elementLookupCount()
  ],
  invalidCoordinateFallback: nearest(invalidCoordinate.chart, {x: 42}),
  invalidCoordinateElementLookups: invalidCoordinate.elementLookupCount(),
  missingScaleFallback: nearest({
    data: {labels},
    getElementsAtEventForMode: () => [{index: 1}]
  }, {x: 42}),
  missingCoordinateWithoutFallback: nearest({
    data: {labels},
    scales: {x: {getValueForPixel: () => 1}},
    getElementsAtEventForMode: () => []
  }, {}),
  outOfRangeFallback: nearest({
    data: {labels},
    scales: {x: {getValueForPixel: () => NaN}},
    getElementsAtEventForMode: () => [{index: labels.length}]
  }, {x: 42}),
  missingLabels: nearest({
    scales: {x: {getValueForPixel: () => 0}},
    getElementsAtEventForMode: () => [{index: 0}]
  }, {x: 42})
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
        "beforeFirstClamped": 0,
        "afterLastClamped": 3,
        "coordinateElementLookups": [0, 0, 0, 0, 0],
        "invalidCoordinateFallback": 2,
        "invalidCoordinateElementLookups": 1,
        "missingScaleFallback": 1,
        "missingCoordinateWithoutFallback": -1,
        "outOfRangeFallback": -1,
        "missingLabels": -1,
    }


def test_price_chart_local_plugin_draws_selected_dates_and_persists_on_release():
    app = read("app.js")
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const labels = ['first', 'second', 'third', 'last'];
const config = api.buildPriceChartConfig({
  ohlcv: labels.map(date => ({date, vwap_1d: null}))
});
const plugin = config.plugins.find(candidate => candidate.id === 'priceChartDateSelection');
let updateCount = 0;
const scalePixels = [];
const selectedIndexes = [];
const draws = [];
const contextCalls = {save: 0, restore: 0};
let path = null;
const ctx = {
  save() { contextCalls.save += 1; },
  restore() { contextCalls.restore += 1; },
  setLineDash(dash) { this.dash = [...dash]; },
  beginPath() { path = {}; },
  moveTo(x, y) { path.from = [x, y]; },
  lineTo(x, y) { path.to = [x, y]; },
  stroke() {
    draws.push({
      x: path.from[0],
      top: path.from[1],
      bottom: path.to[1],
      strokeStyle: this.strokeStyle,
      lineWidth: this.lineWidth,
      dash: this.dash
    });
  },
  measureText: () => ({width: 120}),
  fillRect(left, top, width, height) {
    Object.assign(draws[draws.length - 1], {
      labelBackground: {left, top, right: left + width, bottom: top + height}
    });
  },
  fillText(text, x, y, maxWidth) {
    Object.assign(draws[draws.length - 1], {
      label: {text, x, y, maxWidth, color: this.fillStyle}
    });
  }
};
const chart = {
  data: config.data,
  options: config.options,
  chartArea: {left: 10, right: 310, top: 20, bottom: 220},
  ctx,
  scales: {x: {
    getValueForPixel: pixel => {
      scalePixels.push(pixel);
      return pixel / 100;
    },
    getPixelForValue: index => {
      selectedIndexes.push(index);
      return 10 + index * 100;
    }
  }},
  getElementsAtEventForMode: () => {
    throw new Error('normalized x coordinates should select the index');
  },
  update: () => { updateCount += 1; }
};

function dispatch(type, x, inChartArea = true) {
  const args = {event: {type, x}, inChartArea, changed: false};
  plugin.afterEvent(chart, args);
  return {
    changed: args.changed,
    selection: chart.$priceChartDateSelection
      ? {...chart.$priceChartDateSelection}
      : null
  };
}

plugin.afterDatasetsDraw(chart);
const drawsWithoutSelection = draws.length;
const first = dispatch('mousemove', -500);
plugin.afterDatasetsDraw(chart);
const sameFirst = dispatch('mousemove', -100);
const nullDataDate = dispatch('click', 100);
plugin.afterDatasetsDraw(chart);
const mouseRelease = dispatch('mouseup', 0);
plugin.afterDatasetsDraw(chart);
const pointerRelease = dispatch('pointerup', 0);
plugin.afterDatasetsDraw(chart);
const interiorTouch = dispatch('touchstart', 200);
const last = dispatch('touchmove', 999);
plugin.afterDatasetsDraw(chart);
const outside = dispatch('mousemove', 0, false);
const unrelated = dispatch('mouseout', 0);

console.log(JSON.stringify({
  pluginIds: config.plugins.map(candidate => candidate.id),
  hasDrawHook: typeof plugin.afterDatasetsDraw === 'function',
  interaction: config.options.interaction,
  hasTooltip: typeof config.options.plugins.tooltip.callbacks.label === 'function',
  hasPriceAnnotationOptions: Object.hasOwn(config.options.plugins, 'annotation'),
  hasOnClick: Object.hasOwn(config.options, 'onClick'),
  drawsWithoutSelection,
  first,
  sameFirst,
  nullDataDate,
  interiorTouch,
  last,
  outside,
  unrelated,
  mouseRelease,
  pointerRelease,
  everyDatasetNullAtSelectedDate: config.data.datasets.every(dataset => dataset.data[1] === null),
  draws,
  labelsStayInsidePlot: draws.every(draw => (
    draw.labelBackground.left >= chart.chartArea.left &&
    draw.labelBackground.right <= chart.chartArea.right
  )),
  scalePixels,
  selectedIndexes,
  contextCalls,
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

    assert json.loads(completed.stdout) == {
        "pluginIds": ["priceChartDateSelection"],
        "hasDrawHook": True,
        "interaction": {"mode": "index", "axis": "x", "intersect": False},
        "hasTooltip": True,
        "hasPriceAnnotationOptions": False,
        "hasOnClick": False,
        "drawsWithoutSelection": 0,
        "first": {"changed": True, "selection": {"index": 0, "date": "first"}},
        "sameFirst": {"changed": False, "selection": {"index": 0, "date": "first"}},
        "nullDataDate": {"changed": True, "selection": {"index": 1, "date": "second"}},
        "interiorTouch": {"changed": True, "selection": {"index": 2, "date": "third"}},
        "last": {"changed": True, "selection": {"index": 3, "date": "last"}},
        "outside": {"changed": False, "selection": {"index": 3, "date": "last"}},
        "unrelated": {"changed": False, "selection": {"index": 3, "date": "last"}},
        "mouseRelease": {"changed": False, "selection": {"index": 1, "date": "second"}},
        "pointerRelease": {"changed": False, "selection": {"index": 1, "date": "second"}},
        "everyDatasetNullAtSelectedDate": True,
        "draws": [
            {
                "x": 10,
                "top": 20,
                "bottom": 220,
                "strokeStyle": "#2563eb",
                "lineWidth": 2,
                "dash": [4, 3],
                "labelBackground": {"left": 16, "top": 24, "right": 144, "bottom": 42},
                "label": {
                    "text": "선택 날짜 first",
                    "x": 20,
                    "y": 26,
                    "maxWidth": 120,
                    "color": "#1d4ed8",
                },
            },
            {
                "x": 110,
                "top": 20,
                "bottom": 220,
                "strokeStyle": "#2563eb",
                "lineWidth": 2,
                "dash": [4, 3],
                "labelBackground": {"left": 116, "top": 24, "right": 244, "bottom": 42},
                "label": {
                    "text": "선택 날짜 second",
                    "x": 120,
                    "y": 26,
                    "maxWidth": 120,
                    "color": "#1d4ed8",
                },
            },
            {
                "x": 110,
                "top": 20,
                "bottom": 220,
                "strokeStyle": "#2563eb",
                "lineWidth": 2,
                "dash": [4, 3],
                "labelBackground": {"left": 116, "top": 24, "right": 244, "bottom": 42},
                "label": {
                    "text": "선택 날짜 second",
                    "x": 120,
                    "y": 26,
                    "maxWidth": 120,
                    "color": "#1d4ed8",
                },
            },
            {
                "x": 110,
                "top": 20,
                "bottom": 220,
                "strokeStyle": "#2563eb",
                "lineWidth": 2,
                "dash": [4, 3],
                "labelBackground": {"left": 116, "top": 24, "right": 244, "bottom": 42},
                "label": {
                    "text": "선택 날짜 second",
                    "x": 120,
                    "y": 26,
                    "maxWidth": 120,
                    "color": "#1d4ed8",
                },
            },
            {
                "x": 310,
                "top": 20,
                "bottom": 220,
                "strokeStyle": "#2563eb",
                "lineWidth": 2,
                "dash": [4, 3],
                "labelBackground": {"left": 176, "top": 24, "right": 304, "bottom": 42},
                "label": {
                    "text": "선택 날짜 last",
                    "x": 180,
                    "y": 26,
                    "maxWidth": 120,
                    "color": "#1d4ed8",
                },
            },
        ],
        "labelsStayInsidePlot": True,
        "scalePixels": [-500, -100, 100, 200, 999],
        "selectedIndexes": [0, 1, 1, 1, 3],
        "contextCalls": {"save": 5, "restore": 5},
        "updateCount": 0,
    }

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
