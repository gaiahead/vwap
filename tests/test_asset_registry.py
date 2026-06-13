import gen_trend_data as gen


def test_marvell_mrvl_is_registered():
    assert ("Marvell", "MRVL") in gen.ASSETS


def test_sandisk_sndk_is_registered():
    assert ("Sandisk", "SNDK") in gen.ASSETS


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


def test_asset_tickers_are_unique():
    tickers = [ticker for _, ticker in gen.ASSETS]

    assert len(tickers) == len(set(tickers))
