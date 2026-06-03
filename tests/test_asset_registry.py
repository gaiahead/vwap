import gen_trend_data as gen


def test_marvell_mrvl_is_in_ai_global_tech_group():
    assert ("Marvell", "MRVL", "g3") in gen.ASSETS


def test_asset_tickers_are_unique():
    tickers = [ticker for _, ticker, _ in gen.ASSETS]

    assert len(tickers) == len(set(tickers))
