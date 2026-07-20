import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_table_columns_and_default_sort_match_current_dashboard_contract():
    html = read("index.html")
    app = read("app.js")
    generator = read("gen_trend_data.py")
    headers = re.findall(r"<th data-sort=\"[^\"]+\">([^<]+)</th>", html)

    assert headers == [
        "종목",
        "신호 1",
        "신호 2",
        "신호 3",
        "변돌 수익률",
        "1&gt;5&gt;20&gt;60&gt;200 수익률",
        "5&gt;20&gt;60&gt;200 수익률",
        "20&gt;60&gt;200 수익률",
        "200일 수익률",
    ]
    assert "const DEFAULT_SORT = { key: 'alignment_1_5_20_60_200_return_pct', dir: 'desc' }" in app
    assert "key: 'volatility_breakout_return_pct', label: '변돌 수익률'" in app
    assert "key: 'signal_1', label: '신호 1'" in app
    assert "key: 'signal_2', label: '신호 2'" in app
    assert "key: 'signal_3', label: '신호 3'" in app
    assert "strategies?.[ALIGNMENT_1_5_20_60_200]?.latest?.signal" in app
    assert "strategies?.[ALIGNMENT_5_20_60_200]?.latest?.signal" in app
    assert "strategies?.[ALIGNMENT_20_60_200]?.latest?.signal" in app
    assert "key: 'alignment_1_5_20_60_200_return_pct', label: '1>5>20>60>200 수익률'" in app
    assert "key: 'alignment_5_20_60_200_return_pct', label: '5>20>60>200 수익률'" in app
    assert "key: 'alignment_20_60_200_return_pct', label: '20>60>200 수익률'" in app
    assert "rolling200.volatility_breakout_return_pct" in app
    assert "신호 1은 1d &gt; 5d &gt; 20d &gt; 60d &gt; 200d" in html
    assert "신호 2는 5d &gt; 20d &gt; 60d &gt; 200d" in html
    assert "신호 3은 20d &gt; 60d &gt; 200d" in html
    assert "다음 거래일 1d VWAP" in html
    combined = html + app + generator
    for token in ["5/20 괴리율", "5/200 괴리율", "MDD", "mdd", "drawdown"]:
        assert token not in combined
    for legacy_key in ["alignment_1_5_20_200", "alignment_5_20_200"]:
        assert legacy_key not in combined


def test_detail_has_four_clear_strategy_backtest_journals():
    app = read("app.js")
    css = read("style.css")

    for token in [
        "renderBacktestJournals",
        "backtest_journals",
        "변동성 돌파",
        "정배열",
        "초단기",
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

    assert app.count("\n      createJournalCard({") == 4
    assert "createHorizonItem('초단기', '변동성 돌파'" in app
    assert "createHorizonItem('단기', shortLabel" in app
    assert "createHorizonItem('중기', mediumLabel" in app
    assert "createHorizonItem('장기', longLabel" in app
    assert "journals[ALIGNMENT_1_5_20_60_200]" in app
    assert "journals[ALIGNMENT_5_20_60_200]" in app
    assert "journals[ALIGNMENT_20_60_200]" in app
    assert ".journal-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in css

    for selector in [
        ".alignment-tabs",
        ".alignment-tab",
        ".backtest-journal-section",
        ".journal-grid",
        ".journal-card",
        ".journal-card-ultra",
        ".journal-card-short",
        ".journal-card-medium",
        ".journal-card-long",
        ".journal-summary",
        ".journal-table-wrap",
        ".journal-table",
    ]:
        assert selector in css


def test_journal_entry_and_exit_prices_render_as_rounded_integers():
    app = read("app.js")

    assert "function fmtJournalPrice(value)" in app
    assert "toLocaleString('ko-KR', { maximumFractionDigits: 0 })" in app
    assert "fmtJournalPrice(record.entry_price)" in app
    assert "fmtJournalPrice(record.exit_price)" in app
    assert "fmtJournalPrice(record.valuation_price)" in app


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


def test_detail_panels_vp_tabs_and_price_datasets_use_1_5_20_60_200_with_trade_markers():
    app = read("app.js")

    assert "VWAP Lines · 3/5/10/20/40/60/100/200" not in app
    assert "VWAP Lines · 1/5/20/40/60/100/200" not in app
    assert "VWAP Lines · 2/5/20/40/60/100/200" not in app
    assert "Volume Profile" in app
    assert "const VP_PERIODS = ['1d', '5d', '20d', '60d', '200d']" in app
    assert "let currentVpPeriod = '1d';" in app
    assert "currentVpPeriod = '1d';" in app
    assert "const PRICE_DATASET_ORDER = ['BUY', 'SELL', ...PRICE_LINE_DEFS.map(def => def.label)];" in app
    assert "const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, idx) => [label, idx]));" in app
    assert "label.startsWith('VWAP 5')" not in app
    assert "{ label: '1d', window: 1, color: '#eab308', dash: [], width: 1.15 }" in app
    assert "{ label: '5d', window: 5, color: '#dc2626', dash: [], width: 1.15 }" in app
    assert "{ label: '20d', window: 20, color: '#16a34a', dash: [], width: 1.15 }" in app
    assert "{ label: '60d', window: 60, color: '#2563eb', dash: [], width: 1.15 }" in app
    assert "{ label: '200d', window: 200, color: '#000000', dash: [], width: 1.15" in app
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
    assert line_labels == ["1d", "5d", "20d", "60d", "200d", "BUY", "SELL"]


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
