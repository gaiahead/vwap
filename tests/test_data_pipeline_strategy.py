from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Iterable

import pandas as pd
import pytest

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


def test_prepare_strategy_frame_uses_indicator_warmup_but_returns_recent_200_days():
    df = make_ohlcv(range(1, 421))

    work = gen.prepare_strategy_frame(df)

    assert len(work) == gen.LOOKBACK_TRADING_DAYS
    assert work.index[0] == df.index[-gen.LOOKBACK_TRADING_DAYS]
    first = work.iloc[0]
    assert first["vwap_1d"] == (first["high"] + first["low"] + first["close"]) / 3
    assert "vwap_2d" not in work
    assert not work[["vwap_5d", "vwap_20d", "vwap_60d", "vwap_200d"]].isna().any().any()
    source = df.tail(gen.HISTORY_TRADING_DAYS).copy()
    source_proxy = (source["high"] + source["low"] + source["close"]) / 3
    expected_vwap200 = source_proxy.rolling(200).mean()
    assert math.isclose(work["vwap_200d"].iloc[0], expected_vwap200.loc[work.index[0]])
    assert math.isclose(work["vwap_200d"].iloc[-1], source_proxy.iloc[-200:].mean())
    assert not work["vwap_1d"].isna().any()


def test_strategy_available_for_newer_assets_inside_recent_200_day_scope():
    df = make_ohlcv(range(100, 160))

    signal = gen.build_strategy_signal(df)

    assert signal["available"] is True
    assert set(signal["strategies"]) == {
        gen.ALIGNMENT_1_5_20_60_200,
        gen.ALIGNMENT_5_20_60_200,
        gen.ALIGNMENT_20_60_200,
    }
    for strategy in signal["strategies"].values():
        latest = strategy["latest"]
        assert latest["vwap5"] is not None
        assert latest["vwap20"] is not None
        assert latest["vwap60"] is not None
        assert latest["vwap200"] is None
        assert latest["signal"] == "WAIT"
        assert latest["alignment"] == "N/A"
    rolling_200d = signal["backtest"]["rolling_200d"]
    assert rolling_200d["window_days"] == len(df)
    assert rolling_200d["alignment_1_5_20_60_200_return_pct"] is not None
    assert rolling_200d["alignment_5_20_60_200_return_pct"] is not None
    assert rolling_200d["alignment_20_60_200_return_pct"] is not None
    assert rolling_200d["buy_hold_return_pct"] is not None
    assert set(rolling_200d) == {
        "window_days",
        "alignment_1_5_20_60_200_return_pct",
        "alignment_5_20_60_200_return_pct",
        "alignment_20_60_200_return_pct",
        "buy_hold_return_pct",
        "volatility_breakout_return_pct",
    }
    assert signal["backtest"]["volatility_breakout"] == {
        "k": 0.5,
        "trades": len(df) - 2,
        "win_rate_pct": 0.0,
        "entry": "today_open + previous_range * k",
        "exit": "next_day_open",
        "fee_one_way_pct": 0.03,
        "final_day_entry": "skipped_without_next_open",
    }


def test_volatility_breakout_k_half_compounds_completed_next_open_trades():
    idx = pd.bdate_range(start="2026-01-05", periods=5)
    context = pd.DataFrame(
        {
            "open": [100.0, 100.0, 121.0, 130.0, 130.0],
            "high": [110.0, 111.0, 128.0, 131.0, 200.0],
            "low": [90.0, 99.0, 120.0, 129.0, 120.0],
            "close": [100.0, 105.0, 127.0, 130.0, 190.0],
        },
        index=idx,
    )

    result = gen.simulate_volatility_breakout_strategy(context, visible_days=4)

    fee_multiplier = 1 - gen.STRATEGY_FEE_ONE_WAY
    expected_equity = (
        (121.0 / 110.0)
        * (130.0 / 127.0)
        * fee_multiplier**4
    )
    expected_first_trade_return = round(((121.0 / 110.0) * fee_multiplier**2 - 1) * 100, 2)
    assert gen.VOLATILITY_BREAKOUT_K == 0.5
    assert result["k"] == 0.5
    assert result["trades"] == 2
    assert result["journal"] == [
        {
            "entry_date": "2026-01-06",
            "entry_price": 110.0,
            "exit_date": "2026-01-07",
            "exit_price": 121.0,
            "return_pct": expected_first_trade_return,
            "status": "CLOSED",
        },
        {
            "entry_date": "2026-01-07",
            "entry_price": 127.0,
            "exit_date": "2026-01-08",
            "exit_price": 130.0,
            "return_pct": round(((130.0 / 127.0) * fee_multiplier**2 - 1) * 100, 2),
            "status": "CLOSED",
        },
    ]
    assert expected_first_trade_return > 0
    assert math.isclose(result["final_equity"], expected_equity)
    assert math.isclose(result["strategy_return_pct"], (expected_equity - 1) * 100)


def test_volatility_breakout_charges_stock_transaction_tax_even_on_a_loss():
    idx = pd.bdate_range(start="2026-01-05", periods=3)
    context = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [110.0, 111.0, 101.0],
            "low": [90.0, 99.0, 99.0],
            "close": [100.0, 105.0, 100.0],
        },
        index=idx,
    )

    result = gen.simulate_volatility_breakout_strategy(
        context,
        visible_days=2,
        transaction_tax_sell=gen.DOMESTIC_STOCK_TRANSACTION_TAX_SELL,
    )

    expected_equity = (
        (100.0 / 110.0)
        * (1 - gen.STRATEGY_FEE_ONE_WAY)
        * (
            1
            - gen.STRATEGY_FEE_ONE_WAY
            - gen.DOMESTIC_STOCK_TRANSACTION_TAX_SELL
        )
    )
    assert result["trades"] == 1
    assert result["journal"][0]["return_pct"] < 0
    assert math.isclose(result["final_equity"], expected_equity)


def test_each_alignment_charges_stock_transaction_tax_only_when_closed():
    idx = pd.bdate_range(start="2026-01-05", periods=5)
    work = pd.DataFrame(
        {
            "vwap_1d": [110.0, 140.0, 142.0, 110.0, 100.0],
            "vwap_5d": [120.0, 130.0, 130.0, 120.0, 120.0],
            "vwap_20d": [90.0, 120.0, 120.0, 90.0, 90.0],
            "vwap_60d": [100.0] * 5,
            "vwap_200d": [80.0] * 5,
        },
        index=idx,
    )

    expected_equity = (
        (100.0 / 142.0)
        * (1 - gen.STRATEGY_FEE_ONE_WAY)
        * (
            1
            - gen.STRATEGY_FEE_ONE_WAY
            - gen.DOMESTIC_STOCK_TRANSACTION_TAX_SELL
        )
    )

    for strategy_key in gen.ALIGNMENT_STRATEGIES:
        taxable = gen.simulate_alignment_strategy(
            work,
            transaction_tax_sell=gen.DOMESTIC_STOCK_TRANSACTION_TAX_SELL,
            strategy_key=strategy_key,
        )
        fee_only = gen.simulate_alignment_strategy(work, strategy_key=strategy_key)

        assert taxable["in_position"] is False
        assert len(taxable["trades"]) == 1
        assert math.isclose(taxable["final_equity"], expected_equity)
        assert taxable["final_equity"] < fee_only["final_equity"]

        open_work = work.iloc[:3]
        taxable_open = gen.simulate_alignment_strategy(
            open_work,
            transaction_tax_sell=gen.DOMESTIC_STOCK_TRANSACTION_TAX_SELL,
            strategy_key=strategy_key,
        )
        fee_only_open = gen.simulate_alignment_strategy(
            open_work,
            strategy_key=strategy_key,
        )
        assert taxable_open["in_position"] is True
        assert math.isclose(taxable_open["final_equity"], fee_only_open["final_equity"])


def test_build_strategy_signal_applies_ticker_cost_model_to_both_strategies():
    df = make_ohlcv([100] * 220 + [130] * 80 + [82] * 60 + [150] * 60)

    stock = gen.build_strategy_signal(df, ticker="005930.KS")
    etf = gen.build_strategy_signal(df, ticker="069500.KS")

    assert stock["cost_model"]["transaction_tax_sell_pct"] == 0.2
    assert etf["cost_model"]["transaction_tax_sell_pct"] == 0.0
    assert (
        stock["backtest"]["rolling_200d"]["volatility_breakout_return_pct"]
        <= etf["backtest"]["rolling_200d"]["volatility_breakout_return_pct"]
    )
    for field in [
        "alignment_1_5_20_60_200_return_pct",
        "alignment_5_20_60_200_return_pct",
        "alignment_20_60_200_return_pct",
    ]:
        assert (
            stock["backtest"]["rolling_200d"][field]
            <= etf["backtest"]["rolling_200d"][field]
        )


def test_win_rates_use_unrounded_trade_returns():
    fee_multiplier = 1 - gen.STRATEGY_FEE_ONE_WAY
    tiny_winner_exit = 100.0 / (fee_multiplier**2) * 1.000001

    idx = pd.bdate_range(start="2026-04-01", periods=5)
    work = pd.DataFrame(
        {
            "vwap_1d": [99.0, 101.0, 100.0, 99.0, tiny_winner_exit],
            "vwap_5d": [110.0, 90.0, 90.0, 110.0, 110.0],
            "vwap_20d": [80.0] * 5,
            "vwap_60d": [75.0] * 5,
            "vwap_200d": [70.0] * 5,
        },
        index=idx,
    )
    alignment = gen.simulate_alignment_strategy(work)
    assert alignment["trades"][0]["return_pct"] == 0.0

    breakout_context = pd.DataFrame(
        {
            "open": [100.0, 100.0, tiny_winner_exit * 1.1],
            "high": [110.0, 111.0, tiny_winner_exit * 1.11],
            "low": [90.0, 99.0, tiny_winner_exit],
            "close": [100.0, 105.0, tiny_winner_exit * 1.1],
        },
        index=pd.bdate_range(start="2026-05-04", periods=3),
    )
    breakout = gen.simulate_volatility_breakout_strategy(breakout_context, visible_days=2)
    assert breakout["journal"][0]["return_pct"] == 0.0

    summary = gen.build_backtest_summary(
        work,
        {
            gen.ALIGNMENT_1_5_20_60_200: alignment,
            gen.ALIGNMENT_5_20_60_200: alignment,
            gen.ALIGNMENT_20_60_200: alignment,
        },
        breakout,
    )
    assert gen.build_alignment_summary(work, alignment)["win_rate_pct"] == 100.0
    assert summary["volatility_breakout"]["win_rate_pct"] == 100.0


def test_volatility_breakout_skips_final_day_without_next_open():
    idx = pd.bdate_range(start="2026-02-02", periods=3)
    context = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [110.0, 104.0, 200.0],
            "low": [90.0, 96.0, 90.0],
            "close": [100.0, 100.0, 190.0],
        },
        index=idx,
    )

    result = gen.simulate_volatility_breakout_strategy(context, visible_days=2)

    assert result["trades"] == 0
    assert result["journal"] == []
    assert result["final_equity"] == 1.0
    assert result["strategy_return_pct"] == 0.0


def test_strict_alignment_signal_requires_all_values_in_descending_order():
    assert gen.strict_alignment_signal(150, 140, 130, 120, 100) == "BUY"
    assert gen.strict_alignment_signal(140, 130, 120, 100) == "BUY"
    assert gen.strict_alignment_signal(120, 110, 100) == "BUY"
    assert gen.strict_alignment_signal(150, 140, 130, 130, 100) == "SELL"
    assert gen.strict_alignment_signal(150, 140, 110, 120, 100) == "SELL"
    assert gen.strict_alignment_signal(None, 140, 130, 120, 100) == "WAIT"


def test_three_alignment_rules_can_have_different_current_states():
    medium_only = pd.Series({
        "vwap_1d": 110.0,
        "vwap_5d": 130.0,
        "vwap_20d": 120.0,
        "vwap_60d": 110.0,
        "vwap_200d": 100.0,
    })
    long_only = pd.Series({
        "vwap_1d": 90.0,
        "vwap_5d": 100.0,
        "vwap_20d": 120.0,
        "vwap_60d": 110.0,
        "vwap_200d": 100.0,
    })

    assert gen.alignment_signal(medium_only, gen.ALIGNMENT_1_5_20_60_200) == "SELL"
    assert gen.alignment_signal(medium_only, gen.ALIGNMENT_5_20_60_200) == "BUY"
    assert gen.alignment_signal(medium_only, gen.ALIGNMENT_20_60_200) == "BUY"
    assert gen.alignment_signal(long_only, gen.ALIGNMENT_5_20_60_200) == "SELL"
    assert gen.alignment_signal(long_only, gen.ALIGNMENT_20_60_200) == "BUY"


def test_three_alignment_strategies_have_independent_events_and_returns():
    idx = pd.bdate_range(start="2026-06-01", periods=8)
    work = pd.DataFrame(
        {
            "vwap_1d": [30.0, 40.0, 50.0, 120.0, 40.0, 30.0, 30.0, 30.0],
            "vwap_5d": [40.0, 50.0, 100.0, 100.0, 100.0, 50.0, 40.0, 40.0],
            "vwap_20d": [50.0, 80.0, 80.0, 80.0, 80.0, 80.0, 50.0, 50.0],
            "vwap_60d": [70.0] * 8,
            "vwap_200d": [60.0] * 8,
        },
        index=idx,
    )

    simulations = {
        strategy_key: gen.simulate_alignment_strategy(
            work,
            strategy_key=strategy_key,
        )
        for strategy_key in gen.ALIGNMENT_STRATEGIES
    }

    short = simulations[gen.ALIGNMENT_1_5_20_60_200]
    medium = simulations[gen.ALIGNMENT_5_20_60_200]
    long = simulations[gen.ALIGNMENT_20_60_200]
    assert [signal["type"] for signal in short["signals"]] == ["BUY", "SELL"]
    assert [signal["type"] for signal in medium["signals"]] == ["BUY", "SELL"]
    assert [signal["type"] for signal in long["signals"]] == ["BUY", "SELL"]
    assert short["signals"][0]["execution_date"] == gen.date_key(idx[4])
    assert medium["signals"][0]["execution_date"] == gen.date_key(idx[3])
    assert long["signals"][0]["execution_date"] == gen.date_key(idx[2])
    assert len({simulation["final_equity"] for simulation in simulations.values()}) == 3


def test_alignment_strategy_marks_transitions_and_executes_next_day_vwap():
    idx = pd.bdate_range(start="2026-01-05", periods=8)
    states = [False, False, True, True, False, False, True, True]
    rows = []
    for i, aligned in enumerate(states):
        rows.append({
            "vwap_1d": float(110 + i) if not aligned else float(140 + i),
            "vwap_5d": 130.0 if aligned else 120.0,
            "vwap_20d": 120.0 if aligned else 125.0,
            "vwap_60d": 110.0,
            "vwap_200d": 100.0,
        })
    work = pd.DataFrame(rows, index=idx)

    simulation = gen.simulate_alignment_strategy(work)
    signals = simulation["signals"]

    assert [signal["type"] for signal in signals] == ["BUY", "SELL", "BUY"]
    assert all(signal["initial_entry"] is False for signal in signals)
    by_date = {str(dt.date()): row for dt, row in work.iterrows()}
    dates = [str(dt.date()) for dt in work.index]

    for signal in signals:
        signal_index = dates.index(signal["date"])
        assert signal["execution_date"] == dates[signal_index + 1]
        confirmed = by_date[signal["date"]]
        execution = by_date[signal["execution_date"]]
        assert signal["marker_price"] == confirmed["vwap_5d"]
        if signal["type"] == "BUY":
            assert confirmed["vwap_1d"] > confirmed["vwap_5d"] > confirmed["vwap_20d"] > confirmed["vwap_60d"] > confirmed["vwap_200d"]
        else:
            assert not (confirmed["vwap_1d"] > confirmed["vwap_5d"] > confirmed["vwap_20d"] > confirmed["vwap_60d"] > confirmed["vwap_200d"])
        assert signal["price"] == round(float(execution["vwap_1d"]), 4)

    journal = gen.build_alignment_journal(work, simulation)
    assert [row["status"] for row in journal] == ["CLOSED", "OPEN"]
    assert journal[0]["entry_date"] == dates[3]
    assert journal[0]["exit_date"] == dates[5]
    assert journal[0]["holding_days"] == 3
    assert journal[1]["entry_date"] == dates[7]
    assert journal[1]["exit_date"] is None
    assert journal[1]["valuation_date"] == dates[-1]
    assert journal[1]["status"] == "OPEN"


def test_last_day_transition_is_marked_even_without_a_next_day_execution():
    idx = pd.bdate_range(start="2026-01-05", periods=3)
    work = pd.DataFrame(
        {
            "vwap_1d": [110.0, 111.0, 142.0],
            "vwap_5d": [120.0, 120.0, 130.0],
            "vwap_20d": [125.0, 125.0, 120.0],
            "vwap_60d": [110.0, 110.0, 110.0],
            "vwap_200d": [100.0, 100.0, 100.0],
        },
        index=idx,
    )

    simulation = gen.simulate_alignment_strategy(work)

    assert simulation["signals"] == [{
        "date": "2026-01-07",
        "execution_date": None,
        "type": "BUY",
        "initial_entry": False,
        "price": None,
        "marker_price": 130.0,
        "vwap1": 142.0,
        "vwap5": 130.0,
        "vwap20": 120.0,
        "vwap60": 110.0,
        "vwap200": 100.0,
    }]
    assert simulation["in_position"] is False
    assert simulation["final_equity"] == 1.0


def test_alignment_strategies_enter_next_day_when_first_visible_state_is_aligned():
    idx = pd.bdate_range(start="2026-02-02", periods=4)
    work = pd.DataFrame(
        {
            "vwap_1d": [140.0, 141.0, 142.0, 143.0],
            "vwap_5d": [130.0] * 4,
            "vwap_20d": [120.0] * 4,
            "vwap_60d": [110.0] * 4,
            "vwap_200d": [100.0] * 4,
        },
        index=idx,
    )

    for strategy_key in gen.ALIGNMENT_STRATEGIES:
        simulation = gen.simulate_alignment_strategy(work, strategy_key=strategy_key)
        signal = simulation["signals"][0]

        assert signal["date"] == gen.date_key(idx[0])
        assert signal["execution_date"] == gen.date_key(idx[1])
        assert signal["type"] == "BUY"
        assert signal["initial_entry"] is True
        assert signal["price"] == 141.0
        assert simulation["in_position"] is True
        assert simulation["entry_date"] == gen.date_key(idx[1])
        assert simulation["entry_is_initial"] is True
        assert simulation["final_equity"] == pytest.approx(
            (1 - gen.STRATEGY_FEE_ONE_WAY) * 143.0 / 141.0
        )

        journal = gen.build_alignment_journal(work, simulation)
        assert journal == [{
            "entry_date": gen.date_key(idx[1]),
            "entry_price": 141.0,
            "exit_date": None,
            "exit_price": None,
            "valuation_date": gen.date_key(idx[-1]),
            "valuation_price": 143.0,
            "return_pct": pytest.approx(round(((143.0 / 141.0) * (1 - gen.STRATEGY_FEE_ONE_WAY) - 1) * 100, 2)),
            "holding_days": 3,
            "status": "OPEN",
            "initial_entry": True,
        }]


def test_first_evaluable_aligned_state_after_wait_is_an_initial_entry():
    idx = pd.bdate_range(start="2026-02-09", periods=4)
    work = pd.DataFrame(
        {
            "vwap_1d": [140.0, 141.0, 142.0, 143.0],
            "vwap_5d": [130.0] * 4,
            "vwap_20d": [120.0] * 4,
            "vwap_60d": [110.0] * 4,
            "vwap_200d": [None, None, 100.0, 100.0],
        },
        index=idx,
    )

    simulation = gen.simulate_alignment_strategy(work)

    assert simulation["signals"] == [gen.make_signal_record(
        gen.date_key(idx[2]),
        gen.date_key(idx[3]),
        "BUY",
        143.0,
        work.iloc[2],
        initial_entry=True,
    )]
    assert simulation["entry_date"] == gen.date_key(idx[3])
    assert simulation["entry_is_initial"] is True


def test_last_day_first_evaluable_alignment_is_marked_but_not_executed():
    idx = pd.bdate_range(start="2026-02-16", periods=3)
    work = pd.DataFrame(
        {
            "vwap_1d": [140.0, 141.0, 142.0],
            "vwap_5d": [130.0] * 3,
            "vwap_20d": [120.0] * 3,
            "vwap_60d": [110.0] * 3,
            "vwap_200d": [None, None, 100.0],
        },
        index=idx,
    )

    simulation = gen.simulate_alignment_strategy(work)

    assert simulation["signals"][0]["initial_entry"] is True
    assert simulation["signals"][0]["execution_date"] is None
    assert simulation["in_position"] is False
    assert simulation["entry_is_initial"] is False
    assert simulation["final_equity"] == 1.0


def test_build_strategy_keeps_first_day_transition_and_all_200_visible_events(monkeypatch):
    idx = pd.bdate_range(start="2025-01-01", periods=gen.LOOKBACK_TRADING_DAYS + 1)
    states = [False] + [i % 2 == 0 for i in range(gen.LOOKBACK_TRADING_DAYS)]
    rows = []
    for i, aligned in enumerate(states):
        rows.append({
            "vwap_1d": float(140 + i) if aligned else float(110 + i),
            "vwap_5d": 130.0 if aligned else 120.0,
            "vwap_20d": 120.0 if aligned else 90.0,
            "vwap_60d": 110.0,
            "vwap_200d": 100.0,
        })
    context = pd.DataFrame(rows, index=idx)

    def fake_prepare(_df, output_days=gen.LOOKBACK_TRADING_DAYS):
        return context.tail(output_days).copy()

    monkeypatch.setattr(gen, "prepare_strategy_frame", fake_prepare)
    result = gen.build_strategy_signal(make_ohlcv(range(100, 125)))

    assert result["backtest"]["start_date"] == gen.date_key(idx[1])
    for strategy_key in gen.ALIGNMENT_STRATEGIES:
        signals = result["strategies"][strategy_key]["signals"]
        assert len(signals) == gen.LOOKBACK_TRADING_DAYS
        assert signals[0]["date"] == gen.date_key(idx[1])
        assert signals[0]["execution_date"] == gen.date_key(idx[2])
        assert signals[0]["type"] == "BUY"
        assert signals[0]["initial_entry"] is True


def test_trade_return_and_win_rate_include_both_one_way_fees(monkeypatch):
    idx = pd.bdate_range(start="2026-03-02", periods=5)
    work = pd.DataFrame(
        {
            "vwap_1d": [99.0, 101.0, 100.0, 100.0, 100.03],
            "vwap_5d": [110.0, 90.0, 90.0, 110.0, 110.0],
            "vwap_20d": [80.0] * 5,
            "vwap_60d": [75.0] * 5,
            "vwap_200d": [70.0] * 5,
        },
        index=idx,
    )

    simulation = gen.simulate_alignment_strategy(work)
    assert simulation["trades"][0]["return_pct"] < 0
    assert simulation["final_equity"] < 1

    monkeypatch.setattr(gen, "prepare_strategy_frame", lambda _df, output_days=200: work.copy())
    result = gen.build_strategy_signal(make_ohlcv(range(100, 125)))
    strict = result["strategies"][gen.ALIGNMENT_1_5_20_60_200]["backtest"]
    assert strict["trades"] == 1
    assert strict["win_rate_pct"] == 0.0


def test_build_strategy_simulates_visible_window_once_per_alignment(monkeypatch):
    df = make_ohlcv(range(100, 520))
    original = gen.simulate_alignment_strategy
    calls = 0

    def counted_simulation(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(gen, "simulate_alignment_strategy", counted_simulation)

    result = gen.build_strategy_signal(df)

    assert result["available"] is True
    assert calls == len(gen.ALIGNMENT_STRATEGIES) == 3


def test_build_asset_outputs_keeps_trend_and_detail_strategy_contract_in_sync():
    df = make_ohlcv([100] * 220 + [130] * 80 + [82] * 60 + [150] * 60)

    trend, detail = gen.build_asset_outputs("테스트", "TEST", df)

    assert trend["ticker"] == detail["ticker"] == "TEST"
    assert "group" not in trend
    assert trend["strategy_signal"] == detail["strategy_signal"]
    assert "backtest_journals" not in trend
    assert set(detail["backtest_journals"]) == {
        "volatility_breakout",
        gen.ALIGNMENT_1_5_20_60_200,
        gen.ALIGNMENT_5_20_60_200,
        gen.ALIGNMENT_20_60_200,
    }
    assert detail["backtest_journals"]["volatility_breakout"]
    assert all(row["status"] == "CLOSED" for row in detail["backtest_journals"]["volatility_breakout"])
    assert "mdd" not in json.dumps(trend["strategy_signal"], ensure_ascii=False).lower()
    assert trend["lookback_trading_days"] == detail["lookback_trading_days"] == gen.LOOKBACK_TRADING_DAYS
    assert trend["latest_price"] == detail["latest_price"] == round(float(df["close"].iloc[-1]), 2)
    assert gen.WINDOWS == [5, 20, 60, 200]
    assert gen.VOLUME_PROFILE_WINDOWS == [1, 5, 20, 60, 200]
    assert len(detail["ohlcv"]) == gen.LOOKBACK_TRADING_DAYS
    assert detail["ohlcv"][0]["vwap_200d"] is not None
    assert set(detail["volume_profile"]) == {"1d", "5d", "20d", "60d", "200d"}
    for window in gen.WINDOWS:
        assert f"vwap_{window}d" in detail["ohlcv"][-1]
    assert "vwap_1d" in detail["ohlcv"][-1]
    for removed_window in [2, 3, 10, 40, 100]:
        assert f"vwap_{removed_window}d" not in detail["ohlcv"][-1]


def test_insufficient_history_uses_four_strategy_journal_schema():
    df = make_ohlcv(range(100, 120))

    trend, detail = gen.build_asset_outputs("짧은 이력", "SHORT", df)

    assert trend["strategy_signal"]["available"] is False
    assert set(detail["backtest_journals"]) == {
        "volatility_breakout",
        gen.ALIGNMENT_1_5_20_60_200,
        gen.ALIGNMENT_5_20_60_200,
        gen.ALIGNMENT_20_60_200,
    }
    assert all(records == [] for records in detail["backtest_journals"].values())


def test_zero_volume_windows_emit_none_and_json_remains_strict():
    df = make_ohlcv(range(100, 320))
    df["volume"] = 0

    work = gen.prepare_strategy_frame(df)
    assert work["vwap_5d"].iloc[-1] is None
    assert work["vwap_20d"].iloc[-1] is None
    assert work["vwap_60d"].iloc[-1] is None
    assert work["vwap_200d"].iloc[-1] is None

    trend, detail = gen.build_asset_outputs("무거래 테스트", "ZERO", df)
    for strategy in trend["strategy_signal"]["strategies"].values():
        latest = strategy["latest"]
        assert latest["vwap5"] is None
        assert latest["vwap20"] is None
        assert latest["vwap60"] is None
        assert latest["vwap200"] is None
        assert latest["signal"] == "WAIT"
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
