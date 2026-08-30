import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_table_columns_and_default_sort_match_current_dashboard_contract():
    html = read("index.html")
    app = read("app.js")
    generator = read("gen_trend_data.py")
    headers = re.findall(r"<th data-sort=\"[^\"]+\">([^<]+)</th>", html)
    sort_keys = re.findall(r"<th data-sort=\"([^\"]+)\">", html)

    assert headers == [
        "종목",
        "신호 1",
        "신호 2",
        "신호 3",
        "1&gt;5&gt;20&gt;60&gt;120 수익률",
        "5&gt;20&gt;60&gt;120 수익률",
        "20&gt;60&gt;120 수익률",
        "120일 수익률",
    ]
    assert sort_keys == [
        "name",
        "signal_1",
        "signal_2",
        "signal_3",
        "alignment_1_5_20_60_120_return_pct",
        "alignment_5_20_60_120_return_pct",
        "alignment_20_60_120_return_pct",
        "buy_hold_return_pct",
    ]
    assert "const DEFAULT_SORT = { key: 'alignment_1_5_20_60_120_return_pct', dir: 'desc' }" in app
    assert "const ALIGNMENT_SIGNAL_COLUMNS = ALIGNMENT_OPTIONS.map" in app
    assert "const ALIGNMENT_RETURN_COLUMNS = ALIGNMENT_OPTIONS.map" in app
    assert "strategies?.[option.key]?.latest?.signal" in app
    assert "key: `signal_${index + 1}`" in app
    assert "label: `신호 ${index + 1}`" in app
    assert "key: `${option.key}_return_pct`" in app
    assert "label: `${option.label} 수익률`" in app
    assert "rolling_120d?.[`${option.key}_return_pct`]" in app
    assert "rolling_240d" not in app
    for strategy_constant, label, horizon, tone in [
        ("ALIGNMENT_1_5_20_60_120", "1>5>20>60>120", "단기", "short"),
        ("ALIGNMENT_5_20_60_120", "5>20>60>120", "중기", "medium"),
        ("ALIGNMENT_20_60_120", "20>60>120", "장기", "long"),
    ]:
        assert re.search(
            rf"\{{ key: {strategy_constant}, label: '{label}'.+horizon: '{horizon}', tone: '{tone}' \}}",
            app,
        )

    assert "신호 1은 1d &gt; 5d &gt; 20d &gt; 60d &gt; 120d" in html
    assert "신호 2는 5d &gt; 20d &gt; 60d &gt; 120d" in html
    assert "신호 3은 20d &gt; 60d &gt; 120d" in html
    assert "평가 첫날 정배열이면 초기 신호" in html
    assert "다음 거래일 1d VWAP" in html
    combined = html + app + generator
    for token in ["5/20 괴리율", "5/200 괴리율", "drawdown"]:
        assert token not in combined
    for legacy_key in [
        "alignment_1_5_20_200",
        "alignment_5_20_200",
        "alignment_1_5_20_60_200",
        "alignment_5_20_60_200",
        "alignment_20_60_200",
    ]:
        assert legacy_key not in combined


def test_detail_has_four_clear_strategy_backtest_journals():
    app = read("app.js")
    css = read("style.css")

    for token in [
        "renderBacktestJournals",
        "backtest_journals",
        "정배열",
        "단기",
        "중기",
        "장기",
        "진입일",
        "진입가",
        "청산일",
        "청산가",
        "수익률",
    ]:
        assert token in app

    assert "function createAlignmentJournalCard" in app
    assert "최근 120거래일의 정배열 3종과 VWAP20 방향 매매 기록" in app
    assert "최근 120 거래일" in app
    assert "...alignmentContexts.map(context => createAlignmentJournalCard(context, costNote))," in app
    assert "createDirectionJournalCard(directionContext, costNote)" in app
    assert "const alignmentContexts = ALIGNMENT_OPTIONS.map" in app
    assert "createHorizonItem(option.horizon, label, backtest.return_pct, option.tone)" in app
    assert "records: journals[option.key] || []" in app
    for horizon, tone in [("단기", "short"), ("중기", "medium"), ("장기", "long")]:
        assert f"horizon: '{horizon}'" in app
        assert f"tone: '{tone}'" in app
    assert ".journal-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert ".journal-horizon-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))" in css

    for selector in [
        ".alignment-tabs",
        ".alignment-tab",
        ".backtest-journal-section",
        ".journal-grid",
        ".journal-card",
        ".journal-card-short",
        ".journal-card-medium",
        ".journal-card-long",
        ".journal-summary",
        ".journal-table-wrap",
        ".journal-table",
    ]:
        assert selector in css

    for removed in [
        "volatility_breakout",
        "변돌",
        "변동성 돌파",
        "초단기",
        "journal-card-ultra",
        "journal-horizon-ultra",
    ]:
        assert removed not in app + css + read("index.html") + read("gen_trend_data.py")


def test_detail_adds_vwap20_direction_tab_status_colored_slope_and_fourth_journal():
    app = read("app.js")
    css = read("style.css")

    for token in [
        "const VWAP20_DIRECTION = 'vwap20_direction'",
        "label: '20일 방향'",
        "VWAP20 방향 전략",
        "direction-status",
        "direction_change_pct",
        "next_open_action",
        "segment:",
        "mdd_pct",
        "다음 거래일 실제 시초가",
    ]:
        assert token in app

    assert "strategies?.[currentAlignmentStrategy]?.signals" in app
    assert ".journal-card-direction" in css
    assert ".journal-horizon-direction" in css
    assert ".direction-status" in css
    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in css


def test_journal_entry_and_exit_prices_render_as_rounded_integers():
    app = read("app.js")

    assert "function fmtJournalPrice(value)" in app
    assert "toLocaleString('ko-KR', { maximumFractionDigits: 0 })" in app
    assert "fmtJournalPrice(record.entry_price)" in app
    assert "fmtJournalPrice(record.exit_price)" in app
    assert "fmtJournalPrice(record.valuation_price)" in app
    assert "? `초기 · ${fmtJournalDate(record.entry_date)}`" in app
    assert "journal-initial-label" in app


def test_ea_lm_columns_and_lifecycle_score_code_are_removed():
    html = read("index.html")
    app = read("app.js")

    for token in ["EA지수", "LM지수", "Entry Activation", "Late Maturity"]:
        assert token not in html + app

    for token in [
        "ea_score",
        "lm_score",
        "calculateLifecycleScores",
        "fmtIndex",
        "indexColor",
        "longContextGate",
        "lifecycle",
    ]:
        assert token not in app


def test_signal_cell_uses_buy_sell_colors_without_name_indicator():
    app = read("app.js")
    css = read("style.css")

    assert "row-indicator" not in app
    assert "row-indicator" not in css
    assert "setProperty('--c'" not in app
    assert "signal-cell buy" in app
    assert "signal-cell sell" in app
    assert ".signal-cell.buy" in css
    assert ".signal-cell.sell" in css


def test_detail_panels_add_vwap240_range_control_and_keep_trade_markers():
    app = read("app.js")

    assert "const DEFAULT_CHART_TRADING_DAYS = 120;" in app
    assert "const CHART_TRADING_DAY_OPTIONS = [120, 240];" in app
    assert "let currentChartTradingDays = DEFAULT_CHART_TRADING_DAYS;" in app
    assert "const ohlcv = detailData.ohlcv.slice(-currentChartTradingDays);" in app
    assert "chart-range-control" in app
    assert "chart-range-button" in app
    assert "차트 범위" in app
    assert "button.setAttribute('aria-pressed', String(active));" in app
    assert "VWAP Lines · 3/5/10/20/40/60/100/200" not in app
    assert "VWAP Lines · 1/5/20/40/60/100/200" not in app
    assert "VWAP Lines · 2/5/20/40/60/100/200" not in app
    assert "Volume Profile" in app
    assert "const VP_PERIODS = ['1d', '5d', '20d', '60d', '120d', '240d']" in app
    assert "let currentVpPeriod = '1d';" in app
    assert "currentVpPeriod = '1d';" in app
    assert "const PRICE_DATASET_ORDER = ['BUY', 'SELL', ...PRICE_LINE_DEFS.map(def => def.label)];" in app
    assert "const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, idx) => [label, idx]));" in app
    assert "label.startsWith('VWAP 5')" not in app
    for label, window, color in [
        ("1d", 1, "#eab308"),
        ("5d", 5, "#dc2626"),
        ("20d", 20, "#16a34a"),
        ("60d", 60, "#2563eb"),
        ("120d", 120, "#111827"),
        ("240d", 240, "#7c3aed"),
    ]:
        assert re.search(
            rf"label: '{label}', window: {window}, color: '{color}', dash: \[\], width: [\d.]+, opacity: [\d.]+",
            app,
        )
    assert "{ label: '200d', window: 200" not in app
    assert "dash: [5, 3]" not in app
    assert "{ label: '3d'" not in app
    assert "{ label: '10d'" not in app
    assert "{ label: '2d'" not in app
    assert "{ label: '40d'" not in app

    assert "{ label: '100d'" not in app
    assert "pointStyle: 'line'" in app
    assert "lineDash: dataset.borderDash || []" in app
    assert "label: 'BUY'" in app
    assert "label: 'SELL'" in app
    assert "pointStyle: 'triangle'" in app
    assert "pointRotation: 180" in app
    assert "pointBackgroundColor: COLOR.positive" in app
    assert "pointBackgroundColor: COLOR.negative" in app
    assert "label: 'Close'" not in app
    assert "data: closes" not in app
    assert "signalMap" in app
    assert "const ALIGNMENT_OPTIONS" in app
    assert "button.className = 'alignment-tab'" in app
    assert "currentAlignmentStrategy = strategyKey" in app
    assert "strategy_signal?.strategies?.[currentAlignmentStrategy]?.signals" in app
    assert "journals[currentAlignmentStrategy]" not in app

    line_labels = re.findall(r"\{ label: '([^']+)'", app)
    assert line_labels == ["1d", "5d", "20d", "60d", "120d", "240d", "BUY", "SELL"]


def test_chart_visual_trend_helpers_are_buffered_fixed_color_and_read_only():
    app = read("app.js")

    for token in [
        "const VWAP_TREND_LOOKBACK = 3;",
        "const VWAP_TREND_DEADBAND_PCT = 0.04;",
        "const VWAP_TREND_CONFIRMATION_SEGMENTS = 2;",
        "function classifyVwapTrendCandidate",
        "function classifyVwapTrendStates",
        "function getVwapTrendStyle",
        "Object.defineProperty(window, 'VWAP_CHART_TEST_API'",
        "Object.freeze",
    ]:
        assert token in app

    assert "directionMode && def.window === 20" not in app
    assert "current > previous ? COLOR.positive : COLOR.negative" not in app

    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync('app.js', 'utf8').split('\nfetch(`trend_data')[0];
const context = { window: {} };
vm.createContext(context);
vm.runInContext(source, context);
const api = context.window.VWAP_CHART_TEST_API;
const rising = api.classifyVwapTrendStates([100, 100, 100, 100.1, 100.2]);
const falling = api.classifyVwapTrendStates([100, 100, 100, 99.9, 99.8]);
const flat = api.classifyVwapTrendStates([100, 100, 100, 100.03, 100.03]);
const buffered = api.classifyVwapTrendStates([100, 100, 100, 100.1, 100.2, 99.9, 99.8]);
const missing = api.classifyVwapTrendStates([100, 100, 100, 100.1, 100.2, null]);
const styles = {
  rising20: api.getVwapTrendStyle(20, 'rising'),
  flat20: api.getVwapTrendStyle(20, 'flat'),
  falling20: api.getVwapTrendStyle(20, 'falling'),
  rising5: api.getVwapTrendStyle(5, 'rising'),
};
console.log(JSON.stringify({
  rising, falling, flat, buffered, missing, styles,
  frozen: Object.isFrozen(api) && Object.isFrozen(api.lineDefinitions),
  property: Object.getOwnPropertyDescriptor(context.window, 'VWAP_CHART_TEST_API'),
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

    assert result["rising"][-2:] == ["flat", "rising"]
    assert result["falling"][-2:] == ["flat", "falling"]
    assert set(result["flat"]) == {"flat"}
    assert result["buffered"][-3:] == ["rising", "rising", "falling"]
    assert result["missing"][-1] == "flat"
    styles = result["styles"]
    assert styles["rising20"]["borderWidth"] > styles["flat20"]["borderWidth"] > styles["falling20"]["borderWidth"]
    assert styles["rising20"]["opacity"] > styles["flat20"]["opacity"] > styles["falling20"]["opacity"]
    assert styles["rising20"]["borderWidth"] > styles["rising5"]["borderWidth"]
    assert styles["rising20"]["baseColor"] == styles["falling20"]["baseColor"] == "#16a34a"
    assert result["frozen"] is True
    assert result["property"]["writable"] is False
    assert result["property"]["configurable"] is False


def test_chart_toolbar_has_minimal_responsive_css():
    css = read("style.css")

    for selector in [
        ".chart-toolbar",
        ".chart-range-control",
        ".chart-range-label",
        ".chart-range-options",
        ".chart-range-button",
        ".chart-range-button:focus-visible",
    ]:
        assert selector in css
    assert "@media (max-width:640px)" in css


def test_cache_bust_version_is_consistent_everywhere():
    html = read("index.html")
    app = read("app.js")

    style_match = re.search(r'style\.css\?v=([^"\']+)', html)
    script_match = re.search(r'app\.js\?v=([^"\']+)', html)
    app_match = re.search(r"const DATA_VERSION = '([^']+)'", app)

    assert style_match is not None
    assert script_match is not None
    assert app_match is not None
    assert style_match.group(1) == script_match.group(1) == app_match.group(1)


def test_old_matrix_vms_and_strategy_card_ui_are_not_reintroduced():
    app = read("app.js")
    css = read("style.css")

    legacy_tokens = [
        "calcVMS",
        "renderVMS",
        "renderVMSMatrix",
        "getVmsColor",
        "VMS_DECAY",
        "vms_matrix",
        "renderMomentumMatrix",
        "momentum-grid",
        "momentum-cell",
        "strategy-card",
        "strategy-grid",
        "strategy-badge",
        "renderCards",
        "dual-stat",
    ]
    combined = app + css
    for token in legacy_tokens:
        assert token not in combined


def test_refactor_removes_obsolete_frontend_fallbacks_and_gates():
    app = read("app.js")

    for token in [
        "rollingProxyVwap",
        "legendKey",
        "hasMomentumTargets",
        "const targets =",
    ]:
        assert token not in app

    assert app.count("const annotations = {};") == 1
