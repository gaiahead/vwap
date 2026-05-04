from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_user_facing_html_uses_vwap_momentum_and_korean_momentum():
    html = read("index.html")
    assert "VWAP Momentum Market Monitor" in html
    assert "모멘텀" in html
    assert "VMS" not in html


def test_app_code_uses_vwap_momentum_names_not_vms_names():
    app = read("app.js")
    assert "function calcVwapMomentum" in app
    assert "function renderMomentum" in app
    assert "function renderMomentumMatrix" in app
    assert "getMomentumColor" in app
    legacy_tokens = ["calcVMS", "renderVMS", "renderVMSMatrix", "getVmsColor", "VMS_DECAY", "vms_matrix"]
    for token in legacy_tokens:
        assert token not in app


def test_generator_outputs_vwap_momentum_matrix_name():
    generator = read("gen_trend_data.py")
    assert "build_vwap_momentum_matrix" in generator
    assert '"vwap_momentum_matrix"' in generator
    assert "vms_matrix" not in generator
    assert "vms_decay" not in generator


def test_current_detail_json_uses_vwap_momentum_matrix_name():
    detail = read("detail_data/TLT.json")
    assert '"vwap_momentum_matrix"' in detail
    assert '"vms_matrix"' not in detail
