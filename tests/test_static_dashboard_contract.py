import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_DATA_VERSION = "data-20260830-exact-segment-slope"


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


def test_chart_visual_trend_helpers_change_only_width_and_opacity():
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
const widths = {
  rising: api.getVwapTrendStyle(20, 'rising').borderWidth,
  flat: api.getVwapTrendStyle(20, 'flat').borderWidth,
  falling: api.getVwapTrendStyle(20, 'falling').borderWidth,
};
console.log(JSON.stringify({alternating, edgeCases, colors, widths}));
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
    assert result["widths"]["rising"] > result["widths"]["flat"] > result["widths"]["falling"]
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
