import gen_trend_data as gen


def test_marvell_mrvl_is_in_ai_global_tech_group():
    assert ("Marvell", "MRVL", "g3") in gen.ASSETS


def test_sol_frontend_replaces_tiger_us_dividend_dow_jones_in_core_group():
    assert ("SOL 반도체전공정", "475300.KS", "g1") in gen.ASSETS
    assert ("TIGER 미국배당다우존스", "458730.KS", "g1") not in gen.ASSETS


def test_requested_korean_ai_semiconductor_etfs_are_in_korea_semiconductor_group():
    requested_assets = {
        ("ACE AI반도체TOP3+", "469150.KS", "g4"),
        ("SOL 반도체후공정", "475310.KS", "g4"),
        ("SOL AI반도체소부장", "455850.KS", "g4"),
    }

    assert requested_assets <= set(gen.ASSETS)


def test_requested_kodex_ai_power_equipment_etf_is_in_korea_theme_group():
    assert ("KODEX AI전력핵심설비", "487240.KS", "g5") in gen.ASSETS


def test_asset_tickers_are_unique():
    tickers = [ticker for _, ticker, _ in gen.ASSETS]

    assert len(tickers) == len(set(tickers))
