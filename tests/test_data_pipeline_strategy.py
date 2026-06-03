from __future__ import annotations

import json
import math
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
    assert pd.isna(work["vwap_5d"].iloc[3])
    assert work["vwap_5d"].iloc[4] == work["vwap_1d"].iloc[:5].mean()
    assert pd.isna(work["vwap_20d"].iloc[18])
    assert math.isclose(work["vwap_20d"].iloc[19], work["vwap_1d"].iloc[:20].mean())
    assert math.isclose(work["vwap_200d"].iloc[-1], work["vwap_1d"].mean())
    assert not work["vwap_1d"].isna().any()


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

    trend, detail = gen.build_asset_outputs("테스트", "TEST", "g1", df)

    assert trend["ticker"] == detail["ticker"] == "TEST"
    assert trend["group"] == "g1"
    assert trend["strategy_signal"] == detail["strategy_signal"]
    assert trend["lookback_trading_days"] == detail["lookback_trading_days"] == gen.LOOKBACK_TRADING_DAYS
    assert trend["latest_price"] == detail["latest_price"] == round(float(df["close"].iloc[-1]), 2)
    assert set(detail["volume_profile"]) == {"5d", "20d", "200d"}


def test_zero_volume_windows_emit_none_and_json_remains_strict():
    df = make_ohlcv(range(100, 320))
    df["volume"] = 0

    work = gen.prepare_strategy_frame(df)
    assert work["vwap_5d"].iloc[-1] is None
    assert work["vwap_20d"].iloc[-1] is None
    assert work["vwap_200d"].iloc[-1] is None

    trend, detail = gen.build_asset_outputs("무거래 테스트", "ZERO", "g1", df)
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

    trend, detail = gen.build_asset_outputs("KRX 테스트", "000000.KS", "g4", df)
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
