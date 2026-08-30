from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pytest

import gen_trend_data as gen


ALIGNMENT_KEYS = {
    "alignment_1_5_20",
    "alignment_5_20_60",
    "alignment_20_60_120",
}
LATEST_KEYS = {
    "date",
    "vwap1",
    "vwap5",
    "vwap20",
    "vwap60",
    "vwap120",
    "signal",
    "alignment",
}
RETIRED_SCHEMA_KEYS = {
    "backtest",
    "backtest_journals",
    "cost_model",
    "signals",
    "events",
    "trades",
    "rules",
    "lookback_trading_days",
}


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


def walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(walk_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(walk_keys(item) for item in value))
    return set()


def test_storage_frame_keeps_480_rows_for_vwap240_warmup_and_visibility():
    df = make_ohlcv(range(1, 601))

    work = gen.prepare_storage_frame(df)

    assert gen.STORAGE_TRADING_DAYS == 480
    assert gen.HISTORY_TRADING_DAYS == gen.STORAGE_TRADING_DAYS == 480
    assert gen.DOWNLOAD_CALENDAR_DAYS == 1300
    assert len(work) == gen.STORAGE_TRADING_DAYS
    assert work.index[0] == df.index[-gen.STORAGE_TRADING_DAYS]
    assert work.iloc[0]["vwap_1d"] == (
        work.iloc[0]["high"] + work.iloc[0]["low"] + work.iloc[0]["close"]
    ) / 3
    assert "vwap_2d" not in work
    assert pd.isna(work.iloc[0]["vwap_240d"])
    assert not pd.isna(work.iloc[-240]["vwap_240d"])
    source_proxy = (work["high"] + work["low"] + work["close"]) / 3
    assert math.isclose(work["vwap_120d"].iloc[-1], source_proxy.iloc[-120:].mean())
    assert math.isclose(work["vwap_240d"].iloc[-1], source_proxy.iloc[-240:].mean())


def test_current_signal_schema_has_exact_three_alignments_and_latest_snapshot_only():
    signal = gen.build_strategy_signal(make_ohlcv(range(100, 521)))

    assert set(signal) == {"available", "strategies"}
    assert signal["available"] is True
    assert set(signal["strategies"]) == ALIGNMENT_KEYS
    expected_definitions = {
        gen.ALIGNMENT_1_5_20: {
            "label": "1 > 5 > 20",
            "rule": "VWAP1 > VWAP5 > VWAP20",
            "windows": [1, 5, 20],
        },
        gen.ALIGNMENT_5_20_60: {
            "label": "5 > 20 > 60",
            "rule": "VWAP5 > VWAP20 > VWAP60",
            "windows": [5, 20, 60],
        },
        gen.ALIGNMENT_20_60_120: {
            "label": "20 > 60 > 120",
            "rule": "VWAP20 > VWAP60 > VWAP120",
            "windows": [20, 60, 120],
        },
    }
    for key, payload in signal["strategies"].items():
        assert set(payload) == {"label", "rule", "windows", "latest"}
        assert {
            field: payload[field]
            for field in ("label", "rule", "windows")
        } == expected_definitions[key]
        assert set(payload["latest"]) == LATEST_KEYS
        assert payload["latest"]["signal"] in {"BUY", "SELL", "WAIT"}

    for obsolete_windows in ((1, 5, 20, 60, 120), (5, 20, 60, 120)):
        obsolete_constant = "ALIGNMENT_" + "_".join(map(str, obsolete_windows))
        assert not hasattr(gen, obsolete_constant)

    assert not (walk_keys(signal) & RETIRED_SCHEMA_KEYS)
    serialized = json.dumps(signal, ensure_ascii=False, allow_nan=False)
    for token in ["vwap20_direction", "journal", "event", "return_pct", "mdd_pct"]:
        assert token not in serialized.lower()


def test_newer_assets_evaluate_only_signals_with_complete_window_history():
    signal = gen.build_strategy_signal(make_ohlcv(range(100, 160)))

    assert signal["available"] is True
    assert set(signal["strategies"]) == ALIGNMENT_KEYS
    latest_by_key = {
        key: strategy["latest"]
        for key, strategy in signal["strategies"].items()
    }
    assert all(latest["vwap5"] is not None for latest in latest_by_key.values())
    assert all(latest["vwap20"] is not None for latest in latest_by_key.values())
    assert all(latest["vwap60"] is not None for latest in latest_by_key.values())
    assert all(latest["vwap120"] is None for latest in latest_by_key.values())
    assert latest_by_key[gen.ALIGNMENT_1_5_20]["signal"] == "BUY"
    assert latest_by_key[gen.ALIGNMENT_5_20_60]["signal"] == "BUY"
    assert latest_by_key[gen.ALIGNMENT_20_60_120]["signal"] == "WAIT"
    assert latest_by_key[gen.ALIGNMENT_20_60_120]["alignment"] == "N/A"


def test_insufficient_history_keeps_schema_and_marks_only_incomplete_signals_wait():
    signal = gen.build_strategy_signal(make_ohlcv(range(100, 120)))

    assert set(signal) == {"available", "reason", "strategies"}
    assert signal["available"] is False
    assert signal["reason"] == "insufficient_recent_history"
    assert set(signal["strategies"]) == ALIGNMENT_KEYS
    assert all(set(payload) == {"label", "rule", "windows", "latest"} for payload in signal["strategies"].values())
    assert signal["strategies"][gen.ALIGNMENT_1_5_20]["latest"]["signal"] == "BUY"
    assert signal["strategies"][gen.ALIGNMENT_5_20_60]["latest"]["signal"] == "WAIT"
    assert signal["strategies"][gen.ALIGNMENT_20_60_120]["latest"]["signal"] == "WAIT"
    assert not (walk_keys(signal) & RETIRED_SCHEMA_KEYS)


def test_strict_alignment_signal_requires_all_values_in_descending_order():
    assert gen.strict_alignment_signal(150, 140, 130, 120, 100) == "BUY"
    assert gen.strict_alignment_signal(140, 130, 120, 100) == "BUY"
    assert gen.strict_alignment_signal(120, 110, 100) == "BUY"
    assert gen.strict_alignment_signal(150, 140, 130, 130, 100) == "SELL"
    assert gen.strict_alignment_signal(150, 140, 110, 120, 100) == "SELL"
    assert gen.strict_alignment_signal(None, 140, 130, 120, 100) == "WAIT"


def test_signal_1_ignores_vwap60_and_vwap120_that_would_fail_the_old_rule():
    row = pd.Series(
        {
            "vwap_1d": 130.0,
            "vwap_5d": 120.0,
            "vwap_20d": 110.0,
            "vwap_60d": 115.0,
            "vwap_120d": 125.0,
        }
    )

    assert gen.alignment_signal(row, gen.ALIGNMENT_1_5_20) == "BUY"


def test_signal_2_ignores_vwap120_that_would_fail_the_old_rule():
    row = pd.Series(
        {
            "vwap_1d": 90.0,
            "vwap_5d": 130.0,
            "vwap_20d": 120.0,
            "vwap_60d": 110.0,
            "vwap_120d": 115.0,
        }
    )

    assert gen.alignment_signal(row, gen.ALIGNMENT_5_20_60) == "BUY"


def test_signal_3_keeps_the_20_60_120_rule():
    buy_row = pd.Series(
        {
            "vwap_20d": 120.0,
            "vwap_60d": 110.0,
            "vwap_120d": 100.0,
        }
    )
    sell_row = buy_row.copy()
    sell_row["vwap_120d"] = 115.0

    assert gen.alignment_signal(buy_row, gen.ALIGNMENT_20_60_120) == "BUY"
    assert gen.alignment_signal(sell_row, gen.ALIGNMENT_20_60_120) == "SELL"


def test_asset_outputs_keep_registry_detail_parity_and_live_only_schema():
    df = make_ohlcv(range(1, 601))

    trend, detail = gen.build_asset_outputs("테스트", "TEST", df)

    assert set(trend) == {"ticker", "strategy_signal"}
    assert set(detail) == {"name", "ticker", "ohlcv", "volume_profile", "strategy_signal"}
    assert trend["ticker"] == detail["ticker"] == "TEST"
    assert trend["strategy_signal"] == detail["strategy_signal"]
    assert not (walk_keys(trend) & RETIRED_SCHEMA_KEYS)
    assert not (walk_keys(detail) & RETIRED_SCHEMA_KEYS)
    assert gen.WINDOWS == [5, 20, 60, 120, 240]
    assert gen.VOLUME_PROFILE_WINDOWS == [1, 5, 20, 60, 120, 240]
    assert len(detail["ohlcv"]) == 480
    assert detail["ohlcv"][0]["vwap_120d"] is None
    assert detail["ohlcv"][-240]["vwap_120d"] is not None
    assert detail["ohlcv"][0]["vwap_240d"] is None
    assert detail["ohlcv"][-240]["vwap_240d"] is not None
    assert set(detail["volume_profile"]) == {"1d", "5d", "20d", "60d", "120d", "240d"}
    for period, profile in detail["volume_profile"].items():
        latest_rolling_vwap = detail["ohlcv"][-1][f"vwap_{period}"]
        assert profile["vwap"] == pytest.approx(latest_rolling_vwap, abs=0.0001)
    for window in gen.WINDOWS:
        assert f"vwap_{window}d" in detail["ohlcv"][-1]
    assert "vwap_1d" in detail["ohlcv"][-1]
    for removed_window in [2, 3, 10, 40, 100, 200]:
        assert f"vwap_{removed_window}d" not in detail["ohlcv"][-1]
    json.dumps(trend, allow_nan=False)
    json.dumps(detail, allow_nan=False)


def test_volume_profile_vwap_uses_the_matching_exact_rolling_calculation():
    rows = 300
    prices = [100 + index * 0.25 for index in range(rows)]
    df = pd.DataFrame(
        {
            "open": prices,
            "high": [price + 1 + index % 4 for index, price in enumerate(prices)],
            "low": [price - 0.5 - index % 3 * 0.25 for index, price in enumerate(prices)],
            "close": [price + 0.5 for price in prices],
            "volume": [10_000 + index * 137 for index in range(rows)],
        },
        index=pd.bdate_range(start="2025-01-01", periods=rows),
    )

    detail = gen.build_detail_data("VWAP 테스트", "TEST", df)
    latest = detail["ohlcv"][-1]

    for period, profile in detail["volume_profile"].items():
        assert profile["vwap"] == pytest.approx(
            latest[f"vwap_{period}"],
            abs=0.0001,
        ), period


def test_top_level_metadata_has_storage_but_no_retired_lookback(monkeypatch):
    monkeypatch.setattr(gen, "ASSETS", [("테스트", "TEST.KS")])
    monkeypatch.setattr(
        gen,
        "process_asset",
        lambda name, ticker, end_date: (
            {"ticker": ticker, "storage_trading_days": 480},
            {"ticker": ticker, "storage_trading_days": 480},
        ),
    )

    trend, details, failed = gen.collect_asset_outputs("2026-08-30 12:00", "2026-08-30")

    assert trend["_meta"] == {
        "updated_at": "2026-08-30 12:00",
        "storage_trading_days": 480,
    }
    assert set(details) == {"TEST.KS"}
    assert failed == []
    assert "lookback_trading_days" not in json.dumps(trend)


def test_zero_volume_windows_emit_none_and_json_remains_strict():
    df = make_ohlcv(range(100, 320))
    df["volume"] = 0

    trend, detail = gen.build_asset_outputs("무거래 테스트", "ZERO", df)
    for strategy in trend["strategy_signal"]["strategies"].values():
        latest = strategy["latest"]
        assert latest["vwap5"] is None
        assert latest["vwap20"] is None
        assert latest["vwap60"] is None
        assert latest["vwap120"] is None
        assert latest["signal"] == "WAIT"
        assert latest["alignment"] == "N/A"
    assert trend["strategy_signal"] == detail["strategy_signal"]
    json.dumps(trend, allow_nan=False)
    json.dumps(detail, allow_nan=False)


def test_generator_source_removes_backtest_only_builders_and_models():
    source = Path(gen.__file__).read_text(encoding="utf-8").lower()
    for token in [
        "backtest",
        "journal",
        "vwap20_direction",
        "cost_model",
        "strategy_fee",
        "transaction_tax",
        "simulate_alignment",
        "build_alignment_events",
        "make_signal_record",
        "rolling_returns",
        "buy_hold",
        "calc_mdd",
        "win_rate",
        "equity_curve",
        "prepare_strategy_frame",
        "lookback_trading_days",
    ]:
        assert token not in source


def test_write_json_file_rejects_non_finite_values(tmp_path):
    path = tmp_path / "strict.json"

    with pytest.raises(ValueError):
        gen.write_json_file(str(path), {"bad": float("nan")})


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
