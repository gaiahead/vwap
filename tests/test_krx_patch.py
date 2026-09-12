from typing import Iterable
from datetime import date, datetime
import pandas as pd
import gen_trend_data as gen

def make_ohlcv(prices: Iterable[float], start: str = "2025-01-01") -> pd.DataFrame:
    price_list = list(prices)
    idx = pd.bdate_range(start=start, periods=len(price_list))
    return pd.DataFrame(
        {
            "open": price_list,
            "high": [p + 3 for p in price_list],
            "low": [p - 3 for p in price_list],
            "close": price_list,
            "volume": [1_000_000] * len(price_list),
        },
        index=idx,
    )

def test_krx_today_patch_overwrites_existing_same_day_yfinance_row(monkeypatch):
    today = date(2026, 6, 8)
    df = make_ohlcv([100, 110, 120], start="2026-06-04")
    df.index = pd.to_datetime(["2026-06-04", "2026-06-05", "2026-06-08"])

    def fake_fetch(symbol, target_date):
        assert symbol == "069500"
        assert target_date == today
        return {
            "date": target_date,
            "open": 119015.0,
            "high": 125665.0,
            "low": 117930.0,
            "close": 119560.0,
            "volume": 25087331,
        }

    monkeypatch.setattr(gen, "fetch_naver_daily_ohlcv", fake_fetch)
    patched = gen.maybe_patch_krx_today(df, "069500.KS", today)

    latest = patched.iloc[-1]
    assert str(patched.index[-1])[:10] == "2026-06-08"
    assert latest["open"] == 119015.0
    assert latest["high"] == 125665.0
    assert latest["low"] == 117930.0
    assert latest["close"] == 119560.0
    assert latest["volume"] == 25087331
    assert patched.attrs["krx_today_patched"] is True
    assert patched.attrs["krx_today_source"] == "naver_siseJson"

def test_krx_today_patch_skips_unconfirmed_intraday_naver_row(monkeypatch):
    today = date(2026, 6, 24)
    df = make_ohlcv([100, 110, 120], start="2026-06-22")
    df.index = pd.to_datetime(["2026-06-22", "2026-06-23", "2026-06-24"])
    called = False

    def fake_fetch(symbol, target_date):
        nonlocal called
        called = True
        return {
            "date": target_date,
            "open": 1.0,
            "high": 2.0,
            "low": 1.0,
            "close": 2.0,
            "volume": 3,
        }

    monkeypatch.setattr(gen, "fetch_naver_daily_ohlcv", fake_fetch)
    patched = gen.maybe_patch_krx_today(
        df,
        "069500.KS",
        today,
        now=datetime(2026, 6, 24, 10, 27, tzinfo=gen.KST),
    )

    assert called is False
    assert patched.equals(df)
    assert "krx_today_patched" not in patched.attrs

def test_krx_today_patch_allows_confirmed_after_close_naver_row(monkeypatch):
    today = date(2026, 6, 24)
    df = make_ohlcv([100, 110, 120], start="2026-06-22")
    df.index = pd.to_datetime(["2026-06-22", "2026-06-23", "2026-06-24"])

    monkeypatch.setattr(
        gen,
        "fetch_naver_daily_ohlcv",
        lambda symbol, target_date: {
            "date": target_date,
            "open": 119015.0,
            "high": 125665.0,
            "low": 117930.0,
            "close": 119560.0,
            "volume": 25087331,
        },
    )
    patched = gen.maybe_patch_krx_today(
        df,
        "069500.KS",
        today,
        now=datetime(2026, 6, 24, 16, 0, tzinfo=gen.KST),
    )

    assert patched.iloc[-1]["open"] == 119015.0
    assert patched.iloc[-1]["close"] == 119560.0
    assert patched.attrs["krx_today_patched"] is True
    assert patched.attrs["krx_today_source"] == "naver_siseJson"
