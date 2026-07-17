import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_table_columns_and_default_sort_match_current_dashboard_contract():
    html = read("index.html")
    app = read("app.js")
    headers = re.findall(r"<th data-sort=\"[^\"]+\">([^<]+)</th>", html)

    assert headers == [
        "종목",
        "5/20 괴리율",
        "5/200 괴리율",
        "200일 수익률",
        "200일 MDD",
    ]
    assert "const DEFAULT_SORT = { key: 'vwap_5_20_return_pct', dir: 'desc' }" in app
    assert "5/20과 5/200은 각각 단기·장기 VWAP 대비 괴리율" in html
    assert "5/20 수익률" not in html
    assert "5/200 수익률" not in html
    assert "label: '5/20 괴리율'" in app
    assert "label: '5/200 괴리율'" in app


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


def test_asset_name_column_has_no_signal_color_indicator():
    app = read("app.js")
    css = read("style.css")

    assert "row-indicator" not in app
    assert "row-indicator" not in css
    assert "setProperty('--c'" not in app


def test_detail_panels_vp_tabs_and_price_datasets_use_2_to_200_design_without_trade_markers():
    app = read("app.js")

    assert "VWAP Lines · 3/5/10/20/40/60/100/200" not in app
    assert "VWAP Lines · 1/5/20/40/60/100/200" not in app
    assert "VWAP Lines · 2/5/20/40/60/100/200" not in app
    assert "Volume Profile" in app
    assert "const VP_PERIODS = ['2d', '5d', '20d', '40d', '60d', '100d', '200d']" in app
    assert "let currentVpPeriod = '2d';" in app
    assert "currentVpPeriod = '2d';" in app
    assert "const PRICE_DATASET_ORDER = PRICE_LINE_DEFS.map(def => def.label);" in app
    assert "const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, idx) => [label, idx]));" in app
    assert "label.startsWith('VWAP 5')" not in app
    assert "{ label: '2d', window: 2, color: '#eab308', dash: [], width: 1.15 }" in app
    assert "{ label: '5d', window: 5, color: '#dc2626', dash: [], width: 1.15 }" in app
    assert "{ label: '20d', window: 20, color: '#16a34a', dash: [], width: 1.15 }" in app
    assert "{ label: '40d', window: 40, color: '#0891b2', dash: [], width: 1.15 }" in app
    assert "{ label: '60d', window: 60, color: '#2563eb', dash: [], width: 1.15 }" in app
    assert "{ label: '100d', window: 100, color: '#1e3a8a', dash: [], width: 1.15 }" in app
    assert "{ label: '200d', window: 200, color: '#000000', dash: [], width: 1.15" in app
    assert "dash: [5, 3]" not in app
    assert "{ label: '3d'" not in app
    assert "{ label: '1d'" not in app
    assert "{ label: '10d'" not in app
    assert "pointStyle: 'line'" in app
    assert "lineDash: dataset.borderDash || []" in app
    assert "label: 'BUY'" not in app
    assert "label: 'SELL'" not in app
    assert "label: 'Close'" not in app
    assert "data: closes" not in app
    assert "signalMap" not in app

    line_labels = re.findall(r"\{ label: '([^']+)'", app)
    assert line_labels == ["2d", "5d", "20d", "40d", "60d", "100d", "200d"]


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
