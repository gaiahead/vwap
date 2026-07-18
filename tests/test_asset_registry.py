import json
from pathlib import Path

import gen_trend_data as gen


ROOT = Path(__file__).resolve().parents[1]
KOREAN_SUFFIXES = (".KS", ".KQ")


def test_only_korean_exchange_listings_are_registered():
    assert gen.ASSETS
    assert all(ticker.endswith(KOREAN_SUFFIXES) for _, ticker in gen.ASSETS)


def test_generated_data_matches_registered_korean_listings():
    expected_names = {name for name, _ in gen.ASSETS}
    expected_tickers = {ticker for _, ticker in gen.ASSETS}
    trend = json.loads((ROOT / "trend_data.json").read_text(encoding="utf-8"))
    actual_names = {name for name in trend if not name.startswith("_")}
    actual_detail_tickers = {path.stem for path in (ROOT / "detail_data").glob("*.json")}

    assert actual_names == expected_names
    assert actual_detail_tickers == expected_tickers
    assert all(ticker.endswith(KOREAN_SUFFIXES) for ticker in actual_detail_tickers)


def test_tiger_us_dividend_dow_jones_is_registered():
    assert ("TIGER 미국배당다우존스", "458730.KS") in gen.ASSETS


def test_requested_korean_ai_semiconductor_etfs_are_registered():
    requested_assets = {
        ("ACE AI반도체TOP3+", "469150.KS"),
        ("SOL 반도체전공정", "475300.KS"),
        ("SOL 반도체후공정", "475310.KS"),
        ("SOL AI반도체소부장", "455850.KS"),
    }

    assert requested_assets <= set(gen.ASSETS)


def test_requested_kodex_ai_power_equipment_etf_is_registered():
    assert ("KODEX AI전력핵심설비", "487240.KS") in gen.ASSETS


def test_requested_tiger_korea_ai_power_equipment_top3_plus_is_registered():
    assert ("TIGER 코리아AI전력기기TOP3플러스", "0117V0.KS") in gen.ASSETS


def test_requested_world_healthcare_biotech_financial_etfs_are_registered():
    requested_assets = {
        ("TIGER 토탈월드스탁액티브", "0060H0.KS"),
        ("KODEX 미국S&P500헬스케어", "453640.KS"),
        ("TIGER 미국나스닥바이오", "203780.KS"),
        ("KODEX 미국S&P500금융", "453650.KS"),
    }

    assert requested_assets <= set(gen.ASSETS)


def test_leeno_industrial_uses_kosdaq_ticker():
    assert ("리노공업", "058470.KQ") in gen.ASSETS
    assert ("리노공업", "058470.KS") not in gen.ASSETS


def test_asset_tickers_are_unique():
    tickers = [ticker for _, ticker in gen.ASSETS]

    assert len(tickers) == len(set(tickers))
