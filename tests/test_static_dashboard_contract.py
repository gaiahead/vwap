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
        "5/20 수익률",
        "5/200 수익률",
        "200일 수익률",
        "200일 MDD",
    ]
    assert "const DEFAULT_SORT = { key: 'vwap_5_20_return_pct', dir: 'desc' }" in app


def test_detail_panels_vp_tabs_and_price_datasets_use_3_to_200_design_without_trade_markers():
    app = read("app.js")

    assert "VWAP Lines · 3/5/10/20/40/60/100/200" in app
    assert "Volume Profile" in app
    assert "const VP_PERIODS = ['3d', '5d', '10d', '20d', '40d', '60d', '100d', '200d']" in app
    assert "const PRICE_DATASET_ORDER = [...PRICE_LINE_DEFS.map(def => def.label), 'Close']" in app
    assert "const legendOrder = new Map(PRICE_DATASET_ORDER.map((label, idx) => [label, idx]));" in app
    assert "label.startsWith('VWAP 5')" not in app
    assert "{ label: '3d', window: 3, color: '#dc2626', dash: [5, 3]" in app
    assert "{ label: '5d', window: 5, color: '#dc2626', dash: []" in app
    assert "{ label: '10d', window: 10, color: '#16a34a', dash: [5, 3]" in app
    assert "{ label: '20d', window: 20, color: '#16a34a', dash: []" in app
    assert "{ label: '40d', window: 40, color: '#2563eb', dash: [5, 3]" in app
    assert "{ label: '60d', window: 60, color: '#2563eb', dash: []" in app
    assert "{ label: '100d', window: 100, color: '#000000', dash: [5, 3]" in app
    assert "{ label: '200d', window: 200, color: '#000000', dash: []" in app
    assert "label: 'BUY'" not in app
    assert "label: 'SELL'" not in app
    assert "signalMap" not in app

    line_labels = re.findall(r"\{ label: '([^']+)'", app)
    assert line_labels[:8] == ["3d", "5d", "10d", "20d", "40d", "60d", "100d", "200d"]


def test_cache_bust_version_is_consistent_everywhere():
    html = read("index.html")
    app = read("app.js")

    style_match = re.search(r'style\.css\?v=(data-\d{8}-\d{4})', html)
    script_match = re.search(r'app\.js\?v=(data-\d{8}-\d{4})', html)
    app_match = re.search(r"const DATA_VERSION = '(data-\d{8}-\d{4})'", app)

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
