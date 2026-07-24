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


def test_requested_korean_humanoid_robot_assets_are_registered():
    requested_assets = {
        ("ACE K휴머노이드로봇산업TOP2+", "0177X0.KS"),
        ("TIGER 코리아휴머노이드로봇산업", "0148J0.KS"),
        ("레인보우로보틱스", "277810.KQ"),
        ("로보티즈", "108490.KQ"),
        ("에스피지", "058610.KQ"),
        ("두산로보틱스", "454910.KS"),
    }

    assert requested_assets <= set(gen.ASSETS)
    assert {"277810.KQ", "108490.KQ", "058610.KQ", "454910.KS"} <= gen.DOMESTIC_STOCK_TICKERS


def test_requested_solar_assets_use_correct_tickers_and_cost_models():
    requested_assets = {
        ("HD현대에너지솔루션", "322000.KS"),
        ("PLUS 태양광&ESS", "457990.KS"),
        ("대명에너지", "389260.KQ"),
        ("신성이엔지", "011930.KS"),
        ("SDN", "099220.KQ"),
    }
    domestic_stocks = {"322000.KS", "389260.KQ", "011930.KS", "099220.KQ"}

    assert requested_assets <= set(gen.ASSETS)
    assert ("PLUS 태양광&ESS", "389260.KS") not in gen.ASSETS
    assert domestic_stocks <= gen.DOMESTIC_STOCK_TICKERS
    assert gen.build_strategy_cost_model("457990.KS")["product_class"] == "DOMESTIC_EQUITY_ETF"


def test_requested_world_healthcare_biotech_financial_etfs_are_registered():
    requested_assets = {
        ("TIGER 토탈월드스탁액티브", "0060H0.KS"),
        ("KODEX 미국S&P500헬스케어", "453640.KS"),
        ("TIGER 미국나스닥바이오", "203780.KS"),
        ("KODEX 미국S&P500금융", "453650.KS"),
    }

    assert requested_assets <= set(gen.ASSETS)


def test_requested_korean_listed_expansion_assets_are_registered():
    requested_assets = {
        ("KODEX 미국S&P500", "379800.KS"),
        ("KODEX 미국나스닥100", "379810.KS"),
        ("HANARO 원자력iSelect", "434730.KS"),
        ("KODEX 증권", "102970.KS"),
        ("KODEX 보험", "140700.KS"),
        ("KODEX 건설", "117700.KS"),
        ("KODEX 운송", "140710.KS"),
        ("TIGER 화장품", "228790.KS"),
        ("KODEX 필수소비재", "266410.KS"),
        ("KODEX 철강", "117680.KS"),
        ("NAVER", "035420.KS"),
        ("카카오", "035720.KS"),
        ("현대차", "005380.KS"),
        ("기아", "000270.KS"),
        ("삼성바이오로직스", "207940.KS"),
        ("셀트리온", "068270.KS"),
        ("알테오젠", "196170.KQ"),
        ("유한양행", "000100.KS"),
        ("두산에너빌리티", "034020.KS"),
        ("HD현대일렉트릭", "267260.KS"),
        ("LS ELECTRIC", "010120.KS"),
        ("효성중공업", "298040.KS"),
        ("한국전력", "015760.KS"),
        ("LG에너지솔루션", "373220.KS"),
        ("POSCO홀딩스", "005490.KS"),
        ("삼성SDI", "006400.KS"),
        ("KB금융", "105560.KS"),
        ("SK텔레콤", "017670.KS"),
        ("삼양식품", "003230.KS"),
        ("크래프톤", "259960.KS"),
    }

    assert requested_assets <= set(gen.ASSETS)


def test_leeno_industrial_uses_kosdaq_ticker():
    assert ("리노공업", "058470.KQ") in gen.ASSETS
    assert ("리노공업", "058470.KS") not in gen.ASSETS


def test_asset_tickers_are_unique():
    tickers = [ticker for _, ticker in gen.ASSETS]

    assert len(tickers) == len(set(tickers))


def test_strategy_cost_models_cover_all_registered_assets_without_overlap():
    tickers = {ticker for _, ticker in gen.ASSETS}
    explicit_groups = [
        gen.DOMESTIC_STOCK_TICKERS,
        gen.LEVERAGED_ETF_TICKERS,
        gen.PENSION_ETF_TICKERS,
    ]

    assert all(group <= tickers for group in explicit_groups)
    assert all(not (left & right) for i, left in enumerate(explicit_groups) for right in explicit_groups[i + 1:])
    assert all(gen.build_strategy_cost_model(ticker)["product_class"] for ticker in tickers)


def test_strategy_cost_models_follow_the_user_account_assumptions():
    domestic_stock = gen.build_strategy_cost_model("005930.KS")
    domestic_equity_etf = gen.build_strategy_cost_model("069500.KS")
    leveraged_etf = gen.build_strategy_cost_model("122630.KS")
    overseas_etf = gen.build_strategy_cost_model("379800.KS")

    assert domestic_stock == {
        "product_class": "DOMESTIC_STOCK",
        "account_basis": "TAXABLE_BROKERAGE",
        "account_label": "일반계좌",
        "fee_one_way_pct": 0.03,
        "transaction_tax_sell_pct": 0.2,
        "income_tax_per_trade_pct": 0.0,
    }
    assert domestic_equity_etf["product_class"] == "DOMESTIC_EQUITY_ETF"
    assert domestic_equity_etf["account_basis"] == "TAXABLE_BROKERAGE"
    assert domestic_equity_etf["transaction_tax_sell_pct"] == 0.0
    assert leveraged_etf["product_class"] == "LEVERAGED_ETF"
    assert leveraged_etf["account_basis"] == "ISA"
    assert leveraged_etf["transaction_tax_sell_pct"] == 0.0
    assert overseas_etf["product_class"] == "OVERSEAS_OR_OTHER_ETF"
    assert overseas_etf["account_basis"] == "PENSION_OR_IRP"
    assert overseas_etf["transaction_tax_sell_pct"] == 0.0
