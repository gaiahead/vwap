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
        "최근 변화",
        "5/20 수익률",
        "5/200 수익률",
        "당기 보유일",
        "당기 수익률",
        "200일 전략 수익률",
        "200일 보유 수익률",
        "200일 전략 MDD",
        "200일 보유 MDD",
    ]
    assert "const DEFAULT_SORT = { key: 'vwap_5_20_return_pct', dir: 'desc' }" in app


def test_detail_panels_vp_tabs_and_price_datasets_use_5_20_200_design():
    app = read("app.js")

    assert "VWAP Lines · 5/20/200" in app
    assert "Volume Profile" in app
    assert "const VP_PERIODS = ['5d', '20d', '200d']" in app
    assert "const PRICE_DATASET_ORDER = ['BUY', 'SELL', 'VWAP 5', 'VWAP 20', 'VWAP 200', 'Close']" in app

    dataset_labels = re.findall(r"\{label: '([^']+)'", app)
    assert dataset_labels[:6] == ["BUY", "SELL", "VWAP 5", "VWAP 20", "VWAP 200", "Close"]


def test_cache_bust_version_is_data_20260604_2208_everywhere():
    html = read("index.html")
    app = read("app.js")

    assert 'style.css?v=data-20260609-1835' in html
    assert 'app.js?v=data-20260609-1835' in html
    assert "const DATA_VERSION = 'data-20260609-1835'" in app


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
