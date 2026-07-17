from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Iterable

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


def test_prepare_strategy_frame_uses_recent_200_days_and_vwap1d_proxy():
    df = make_ohlcv(range(1, 221))

    work = gen.prepare_strategy_frame(df)

    assert len(work) == gen.LOOKBACK_TRADING_DAYS
    assert work.index[0] == df.index[-gen.LOOKBACK_TRADING_DAYS]
    first = work.iloc[0]
    assert first["vwap_1d"] == (first["high"] + first["low"] + first["close"]) / 3
    assert "vwap_2d" not in work
    assert pd.isna(work["vwap_5d"].iloc[3])
    assert work["vwap_5d"].iloc[4] == work["vwap_1d"].iloc[:5].mean()
    assert pd.isna(work["vwap_20d"].iloc[18])
    assert math.isclose(work["vwap_20d"].iloc[19], work["vwap_1d"].iloc[:20].mean())
    assert math.isclose(work["vwap_200d"].iloc[-1], work["vwap_1d"].mean())
    assert not work["vwap_1d"].isna().any()


def test_strategy_available_for_newer_assets_inside_recent_200_day_scope():
    df = make_ohlcv(range(100, 160))

    signal = gen.build_strategy_signal(df)

    assert signal["available"] is True
    assert signal["latest"]["vwap5"] is not None
    assert signal["latest"]["vwap20"] is not None
    assert signal["latest"]["vwap200"] is None
    assert signal["latest"]["vwap_5_20_return_pct"] is not None
    assert signal["latest"]["vwap_5_200_return_pct"] is None
    rolling_200d = signal["backtest"]["rolling_200d"]
    assert rolling_200d["window_days"] == len(df)
    assert rolling_200d["strategy_return_pct"] is not None
    assert rolling_200d["buy_hold_return_pct"] is not None
    assert rolling_200d["strategy_mdd_pct"] is not None
    assert rolling_200d["buy_hold_mdd_pct"] is not None


def test_strategy_signals_use_confirmed_previous_day_and_next_day_vwap_execution():
    # Flat -> rising -> falling sequence creates both BUY and SELL crosses.
    prices = [100] * 35 + [130] * 45 + [82] * 55 + [96] * 65
    work = gen.prepare_strategy_frame(make_ohlcv(prices))

    simulation = gen.simulate_vwap_5_20_strategy(work, record_signals=True)
    signals = simulation["signals"]

    assert {signal["type"] for signal in signals} >= {"BUY", "SELL"}
    by_date = {str(dt.date()): row for dt, row in work.iterrows()}
    dates = [str(dt.date()) for dt in work.index]

    for signal in signals:
        signal_idx = dates.index(signal["date"])
        assert signal["execution_date"] == dates[signal_idx + 1]
        confirmed = by_date[signal["date"]]
        execution = by_date[signal["execution_date"]]
        if signal["type"] == "BUY":
            assert confirmed["vwap_5d"] > confirmed["vwap_20d"]
        else:
            assert confirmed["vwap_5d"] < confirmed["vwap_20d"]
        assert signal["price"] == round(float(execution["vwap_1d"]), 4)


def test_build_asset_outputs_keeps_trend_and_detail_strategy_contract_in_sync():
    df = make_ohlcv([100] * 35 + [130] * 45 + [82] * 55 + [96] * 65)

    trend, detail = gen.build_asset_outputs("테스트", "TEST", df)

    assert trend["ticker"] == detail["ticker"] == "TEST"
    assert "group" not in trend
    assert trend["strategy_signal"] == detail["strategy_signal"]
    assert trend["lookback_trading_days"] == detail["lookback_trading_days"] == gen.LOOKBACK_TRADING_DAYS
    assert trend["latest_price"] == detail["latest_price"] == round(float(df["close"].iloc[-1]), 2)
    assert gen.WINDOWS == [5, 20, 200]
    assert gen.VOLUME_PROFILE_WINDOWS == [1, 5, 20, 200]
    assert set(detail["volume_profile"]) == {"1d", "5d", "20d", "200d"}
    for window in gen.WINDOWS:
        assert f"vwap_{window}d" in detail["ohlcv"][-1]
    assert "vwap_1d" in detail["ohlcv"][-1]
    for removed_window in [2, 3, 10, 40, 60, 100]:
        assert f"vwap_{removed_window}d" not in detail["ohlcv"][-1]


def test_zero_volume_windows_emit_none_and_json_remains_strict():
    df = make_ohlcv(range(100, 320))
    df["volume"] = 0

    work = gen.prepare_strategy_frame(df)
    assert work["vwap_5d"].iloc[-1] is None
    assert work["vwap_20d"].iloc[-1] is None
    assert work["vwap_200d"].iloc[-1] is None

    trend, detail = gen.build_asset_outputs("무거래 테스트", "ZERO", df)
    latest = trend["strategy_signal"]["latest"]
    assert latest["vwap5"] is None
    assert latest["vwap20"] is None
    assert latest["vwap200"] is None
    assert latest["vwap_5_20_return_pct"] is None
    assert latest["vwap_5_200_return_pct"] is None
    assert latest["alignment"] == "N/A"
    assert trend["strategy_signal"] == detail["strategy_signal"]

    json.dumps(trend, allow_nan=False)
    json.dumps(detail, allow_nan=False)


def test_krx_patched_snapshot_preserves_detail_meta_keys():
    df = make_ohlcv(range(100, 320))
    df.attrs["krx_today_patched"] = True
    df.attrs["krx_today_source"] = "naver_siseJson"
    df.attrs["krx_today_date"] = "2026-06-03"

    trend, detail = gen.build_asset_outputs("KRX 테스트", "000000.KS", df)
    assert trend["data_source"] == {
        "latest_krx_daily": "naver_siseJson",
        "latest_krx_date": "2026-06-03",
    }

    detail["_meta"] = gen.build_detail_meta("2026-06-03 09:55", trend)
    assert detail["_meta"] == {
        "updated_at": "2026-06-03 09:55",
        "krx_today_source": "naver_siseJson",
        "krx_today_date": "2026-06-03",
    }
    json.dumps(detail, allow_nan=False)


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

    patched = gen.maybe_patch_krx_today(
        df,
        "069500.KS",
        today,
        now=datetime(2026, 6, 24, 16, 0, tzinfo=gen.KST),
    )

    latest = patched.iloc[-1]
    assert latest["open"] == 119015.0
    assert latest["close"] == 119560.0
    assert patched.attrs["krx_today_patched"] is True
    assert patched.attrs["krx_today_source"] == "naver_siseJson"
