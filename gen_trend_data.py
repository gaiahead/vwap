"""VWAP 추세 데이터 생성기.

yfinance에서 주가 데이터를 받아 정규분포 기반 Volume Profile VWAP를 계산하고,
trend_data.json으로 출력한다.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, cast

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.stats import norm

# ──────────────────────────────────────────────────────────
# 종목 설정
# ──────────────────────────────────────────────────────────
AssetTuple = tuple[str, str]  # (표시명, 티커)

ASSETS: list[AssetTuple] = [
    # 국내 상장 해외시장 / 글로벌 산업 ETF
    ("TIGER 토탈월드스탁액티브",       "0060H0.KS"),
    ("KODEX 미국S&P500",             "379800.KS"),
    ("KODEX 미국나스닥100",           "379810.KS"),
    ("TIGER 미국배당다우존스",         "458730.KS"),
    ("KODEX 미국S&P500금융",          "453650.KS"),
    ("KODEX 미국S&P500헬스케어",       "453640.KS"),
    ("TIGER 미국나스닥바이오",         "203780.KS"),
    ("SOL 미국테크TOP10",            "481190.KS"),
    ("TIME 글로벌AI인공지능액티브",     "456600.KS"),
    ("TIGER 미국필라델피아반도체나스닥", "381180.KS"),
    ("KODEX 미국반도체",              "390390.KS"),
    ("ACE 글로벌반도체TOP4 Plus",     "446770.KS"),

    # 한국 대표지수 / 반도체
    ("KODEX 200",                    "069500.KS"),
    ("KODEX 200 레버리지",             "122630.KS"),
    ("KODEX 코스닥150",               "229200.KS"),
    ("KODEX 코스닥150 레버리지",        "233740.KS"),
    ("KODEX 반도체",                  "091160.KS"),
    ("KODEX AI반도체TOP2플러스",       "395160.KS"),
    ("KODEX AI반도체핵심장비",          "471990.KS"),
    ("ACE AI반도체TOP3+",             "469150.KS"),
    ("SOL 반도체전공정",               "475300.KS"),
    ("SOL 반도체후공정",               "475310.KS"),
    ("SOL AI반도체소부장",             "455850.KS"),
    ("KODEX AI전력핵심설비",            "487240.KS"),
    ("TIGER 코리아AI전력기기TOP3플러스",  "0117V0.KS"),
    ("TIGER 반도체TOP10",             "396500.KS"),
    ("삼성전자",                      "005930.KS"),
    ("삼성전기",                      "009150.KS"),
    ("SK하이닉스",                    "000660.KS"),
    ("한미반도체",                    "042700.KS"),
    ("리노공업",                      "058470.KQ"),

    # 한국 주요 섹터 / 테마
    ("HANARO 원자력iSelect",          "434730.KS"),
    ("두산에너빌리티",                  "034020.KS"),
    ("HD현대일렉트릭",                 "267260.KS"),
    ("LS ELECTRIC",                  "010120.KS"),
    ("효성중공업",                      "298040.KS"),
    ("한국전력",                        "015760.KS"),
    ("KIWOOM 미국원유에너지기업",      "474800.KS"),
    ("KoAct 미국천연가스인프라액티브", "497780.KS"),
    ("RISE 미국천연가스밸류체인",      "0036Z0.KS"),
    ("PLUS 글로벌희토류&전략자원생산기업", "415920.KS"),
    ("PLUS 태양광&ESS",              "389260.KS"),
    ("한화솔루션",                    "009830.KS"),
    ("OCI홀딩스",                    "010060.KS"),
    ("HD현대에너지솔루션",              "322000.KS"),
    ("씨에스윈드",                    "112610.KS"),
    ("씨에스베어링",                  "297090.KQ"),
    ("SK이터닉스",                   "475150.KS"),
    ("KODEX 자동차",                  "091180.KS"),
    ("현대차",                         "005380.KS"),
    ("기아",                           "000270.KS"),
    ("KODEX 은행",                    "091170.KS"),
    ("KB금융",                         "105560.KS"),
    ("KODEX 2차전지산업",              "305720.KS"),
    ("KODEX 철강",                    "117680.KS"),
    ("LG에너지솔루션",                  "373220.KS"),
    ("POSCO홀딩스",                    "005490.KS"),
    ("삼성SDI",                        "006400.KS"),
    ("KODEX 헬스케어",                "266420.KS"),
    ("삼성바이오로직스",                "207940.KS"),
    ("셀트리온",                        "068270.KS"),
    ("알테오젠",                        "196170.KQ"),
    ("유한양행",                        "000100.KS"),
    ("KODEX 조선TOP10",               "0115D0.KS"),
    ("HD현대중공업",                   "329180.KS"),
    ("삼성중공업",                     "010140.KS"),
    ("한화오션",                       "042660.KS"),
    ("KODEX 방산TOP10",               "0080G0.KS"),
    ("한화에어로스페이스",              "012450.KS"),
    ("현대로템",                       "064350.KS"),
    ("LIG디펜스&에어로스페이스",       "079550.KS"),
    ("한국항공우주",                    "047810.KS"),
    ("한화시스템",                    "272210.KS"),
    ("풍산",                          "103140.KS"),
    ("휴니드",                        "005870.KS"),
    ("KODEX 건설",                    "117700.KS"),
    ("KODEX 운송",                    "140710.KS"),
    ("KODEX 금융고배당TOP10",          "498410.KS"),
    ("KODEX 증권",                    "102970.KS"),
    ("KODEX 보험",                    "140700.KS"),
    ("TIGER 소프트웨어",               "157490.KS"),
    ("NAVER",                         "035420.KS"),
    ("카카오",                          "035720.KS"),
    ("KODEX IT",                      "266370.KS"),
    ("TIGER 미디어컨텐츠",             "228810.KS"),
    ("크래프톤",                        "259960.KS"),
    ("KODEX 로봇액티브",               "445290.KS"),
    ("TIGER 화장품",                   "228790.KS"),
    ("KODEX 필수소비재",               "266410.KS"),
    ("삼양식품",                        "003230.KS"),
    ("SK텔레콤",                        "017670.KS"),
]

# 계좌·상품유형별 세금 가정을 ASSETS의 2-tuple 계약과 분리해 관리한다.
# 국내 개별주식만 일반계좌 매도 거래세를 거래별로 차감하고, ETF는
# 사용자가 지정한 계좌(일반/ISA/연금저축·IRP) 안에서 수수료만 반영한다.
DOMESTIC_STOCK_TICKERS: frozenset[str] = frozenset({
    "005930.KS", "009150.KS", "000660.KS", "042700.KS", "058470.KQ",
    "034020.KS", "267260.KS", "010120.KS", "298040.KS", "015760.KS",
    "009830.KS", "010060.KS", "322000.KS", "112610.KS", "297090.KQ",
    "475150.KS", "005380.KS", "000270.KS", "105560.KS", "373220.KS",
    "005490.KS", "006400.KS", "207940.KS", "068270.KS", "196170.KQ",
    "000100.KS", "329180.KS", "010140.KS", "042660.KS", "012450.KS",
    "064350.KS", "079550.KS", "047810.KS", "272210.KS", "103140.KS",
    "005870.KS", "035420.KS", "035720.KS", "259960.KS", "003230.KS",
    "017670.KS",
})
LEVERAGED_ETF_TICKERS: frozenset[str] = frozenset({
    "122630.KS", "233740.KS",
})
PENSION_ETF_TICKERS: frozenset[str] = frozenset({
    "0060H0.KS", "379800.KS", "379810.KS", "458730.KS", "453650.KS",
    "453640.KS", "203780.KS", "481190.KS", "456600.KS", "381180.KS",
    "390390.KS", "446770.KS", "474800.KS", "497780.KS", "0036Z0.KS",
    "415920.KS",
})
WINDOWS: list[int] = [5, 20, 200]  # 1d는 명시적 proxy, 나머지는 상세 차트용 롤링 VWAP 기간
VOLUME_PROFILE_WINDOWS: list[int] = [1, 5, 20, 200]  # 하단 Volume Profile 기간
LOOKBACK_TRADING_DAYS: int = 200
HISTORY_TRADING_DAYS: int = LOOKBACK_TRADING_DAYS + max(WINDOWS)
MIN_STRATEGY_TRADING_DAYS: int = 25  # 신규 종목도 표에 유지하되, 200d 미산출 시 신호는 WAIT
DOWNLOAD_CALENDAR_DAYS: int = 650  # 최근 200일 + VWAP200 지표 warm-up 확보
N_BUCKETS: int = 20
KST: timezone = timezone(timedelta(hours=9))
KRX_TODAY_PATCH_AFTER = time(15, 30)  # 장중 Naver 일봉은 미확정값이므로 15:30 이후만 반영
EXCLUDE_DATES: frozenset[str] = frozenset({"2025-12-31", "2025-12-30", "2025-12-29"})
OUTPUT_PATH: str = "trend_data.json"
DETAIL_DIR: str = "detail_data"


# ──────────────────────────────────────────────────────────
# VWAP 계산
# ──────────────────────────────────────────────────────────
def compute_vwap(df_window: pd.DataFrame) -> float:
    """정규분포 기반 Volume Profile VWAP."""
    vwap, _ = compute_vwap_with_profile(df_window)
    return vwap


def compute_vwap_with_profile(
    df_window: pd.DataFrame,
) -> tuple[float, list[dict[str, float]]]:
    """정규분포 기반 Volume Profile VWAP + 버킷 배열 반환."""
    lo = float(df_window["low"].min())
    hi = float(df_window["high"].max())
    if hi == lo:
        mid = float(df_window["close"].mean())
        return mid, [{"price": mid, "volume": 0.0} for _ in range(N_BUCKETS)]

    bsize = (hi - lo) / N_BUCKETS
    bucket_prices = np.array([lo + (b + 0.5) * bsize for b in range(N_BUCKETS)])
    bvol = np.zeros(N_BUCKETS)

    for _, r in df_window.iterrows():
        mu = (float(r["high"]) + float(r["low"]) + float(r["close"])) / 3
        sigma = (float(r["high"]) - float(r["low"])) / 4
        if sigma == 0:
            idx = min(N_BUCKETS - 1, int((mu - lo) / bsize))
            bvol[idx] += float(r["volume"])
            continue
        weights = norm.pdf(bucket_prices, mu, sigma)
        total_w = weights.sum()
        if total_w > 0:
            bvol += float(r["volume"]) * (weights / total_w)

    total_vol = bvol.sum()
    if total_vol == 0:
        vwap = float(df_window["close"].iloc[-1])
    else:
        vwap = float((bucket_prices * bvol).sum() / total_vol)

    buckets = [
        {"price": round(float(bucket_prices[i]), 4), "volume": round(float(bvol[i]), 2)}
        for i in range(N_BUCKETS)
    ]
    return vwap, buckets


def typical_price_series(df: pd.DataFrame) -> pd.Series:
    """일봉 OHLC의 대표가격 `(high + low + close) / 3`."""
    return (
        cast(pd.Series, df["high"])
        + cast(pd.Series, df["low"])
        + cast(pd.Series, df["close"])
    ) / 3


def compute_proxy_vwap_series(df: pd.DataFrame, window: int) -> list[float | None]:
    """백테스트/전략 신호용 빠른 일봉 VWAP proxy.

    대표가격 = (High + Low + Close) / 3, n일 VWAP = Σ(대표가격×거래량)/Σ거래량.
    거래량 합계가 0인 구간은 JSON에 NaN/Infinity가 새지 않도록 None으로 둔다.
    """
    volume = cast(pd.Series, df["volume"])
    typical = typical_price_series(df)
    pv = typical * volume
    denom = cast(pd.Series, volume.rolling(window).sum()).replace(0, np.nan)
    series = pv.rolling(window).sum() / denom
    return [None if pd.isna(v) else float(v) for v in series.tolist()]


def is_missing(value: Any) -> bool:
    """JSON 직렬화 전에 제거해야 할 None/NaN 계열 값인지 확인."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def safe_round(value: Any, digits: int = 4) -> float | None:
    if is_missing(value):
        return None
    return round(float(value), digits)


def pct_change(start: Any, end: Any) -> float | None:
    if is_missing(start) or is_missing(end):
        return None
    start_float = float(start)
    if start_float == 0:
        return None
    return (float(end) / start_float - 1) * 100


def date_key(value: Any) -> str:
    """DatetimeIndex/Hashable 값을 JSON용 YYYY-MM-DD 문자열로 변환."""
    return str(pd.Timestamp(value).date())


STRATEGY_FEE_ONE_WAY = 0.0003
DOMESTIC_STOCK_TRANSACTION_TAX_SELL = 0.002
VOLATILITY_BREAKOUT_K = 0.5
STRATEGY_RULES: dict[str, Any] = {
    "buy": "VWAP1 > VWAP5 > VWAP20 > VWAP200 alignment starts",
    "sell": "full alignment breaks",
    "execution": "next_day_vwap_1d_proxy",
    "valuation": "vwap_1d_proxy",
    "buy_hold_return": "last_vwap_1d_proxy / first_vwap_1d_proxy - 1",
    "fee_one_way_pct": 0.03,
    "backtest_window_trading_days": LOOKBACK_TRADING_DAYS,
    "carry_in_position": False,
}


def build_strategy_cost_model(ticker: str | None) -> dict[str, Any]:
    """사용자가 지정한 상품별 운용계좌와 거래단계 비용 정책을 반환한다."""
    if ticker in DOMESTIC_STOCK_TICKERS:
        return {
            "product_class": "DOMESTIC_STOCK",
            "account_basis": "TAXABLE_BROKERAGE",
            "account_label": "일반계좌",
            "fee_one_way_pct": STRATEGY_FEE_ONE_WAY * 100,
            "transaction_tax_sell_pct": DOMESTIC_STOCK_TRANSACTION_TAX_SELL * 100,
            "income_tax_per_trade_pct": 0.0,
        }
    if ticker in LEVERAGED_ETF_TICKERS:
        product_class = "LEVERAGED_ETF"
        account_basis = "ISA"
        account_label = "ISA"
    elif ticker in PENSION_ETF_TICKERS:
        product_class = "OVERSEAS_OR_OTHER_ETF"
        account_basis = "PENSION_OR_IRP"
        account_label = "연금저축/IRP"
    else:
        product_class = "DOMESTIC_EQUITY_ETF"
        account_basis = "TAXABLE_BROKERAGE"
        account_label = "일반계좌"
    return {
        "product_class": product_class,
        "account_basis": account_basis,
        "account_label": account_label,
        "fee_one_way_pct": STRATEGY_FEE_ONE_WAY * 100,
        "transaction_tax_sell_pct": 0.0,
        "income_tax_per_trade_pct": 0.0,
    }


def prepare_strategy_frame(
    df: pd.DataFrame,
    output_days: int = LOOKBACK_TRADING_DAYS,
) -> pd.DataFrame:
    """VWAP 지표를 계산한 뒤 요청한 최근 거래일 구간만 반환한다.

    비즈니스 기준:
    - 수익률·신호 이벤트 범위는 최근 200거래일만 사용한다.
    - VWAP200은 미래 참조 없이 계산하기 위해 이전 199거래일을 지표 warm-up으로만 사용한다.
    - 최근 200일 시작 전 포지션은 이월하지 않는다.
    - 1일 VWAP proxy = (High + Low + Close) / 3.
    - 정배열은 1d > 5d > 20d > 200d 순서다.
    """
    source_days = max(1, int(output_days)) + max(WINDOWS) - 1
    source = df.tail(source_days).copy()
    source["vwap_1d"] = typical_price_series(source).astype(float)
    for window in WINDOWS:
        source[f"vwap_{window}d"] = compute_proxy_vwap_series(source, window)
    return source.tail(output_days).copy()


def full_alignment_signal(vwap1: Any, vwap5: Any, vwap20: Any, vwap200: Any) -> str:
    """확정된 1d/5d/20d/200d 배열을 BUY/SELL/WAIT로 변환."""
    values = [vwap1, vwap5, vwap20, vwap200]
    if any(is_missing(value) for value in values):
        return "WAIT"
    v1, v5, v20, v200 = (float(value) for value in values)
    if v1 > v5 > v20 > v200:
        return "BUY"
    return "SELL"


def alignment_state(row: pd.Series) -> bool | None:
    """한 행의 정배열 상태를 `True`/`False`/미산출 `None`으로 반환."""
    signal = full_alignment_signal(
        row.get("vwap_1d"),
        row.get("vwap_5d"),
        row.get("vwap_20d"),
        row.get("vwap_200d"),
    )
    if signal == "WAIT":
        return None
    return signal == "BUY"


def make_signal_record(
    signal_date: str,
    execution_date: str | None,
    signal_type: str,
    execution_price: float | None,
    confirmed: pd.Series,
) -> dict[str, Any]:
    """차트 마커와 익일 체결 검증에 사용하는 정배열 전환 레코드."""
    return {
        "date": signal_date,
        "execution_date": execution_date,
        "type": signal_type,
        "price": safe_round(execution_price, 4),
        "marker_price": safe_round(confirmed.get("vwap_5d"), 4),
        "vwap1": safe_round(confirmed.get("vwap_1d"), 8),
        "vwap5": safe_round(confirmed.get("vwap_5d"), 8),
        "vwap20": safe_round(confirmed.get("vwap_20d"), 8),
        "vwap200": safe_round(confirmed.get("vwap_200d"), 8),
    }


def build_full_alignment_events(
    work: pd.DataFrame,
    previous_state: bool | None = None,
) -> list[dict[str, Any]]:
    """최근 구간 안에서 발생한 정배열 시작/해제 전환만 추출한다."""
    events: list[dict[str, Any]] = []
    for i, (dt, row) in enumerate(work.iterrows()):
        current_state = alignment_state(row)
        if previous_state is not None and current_state is not None and current_state != previous_state:
            execution_date = date_key(work.index[i + 1]) if i + 1 < len(work) else None
            execution_price = float(work.iloc[i + 1]["vwap_1d"]) if i + 1 < len(work) else None
            events.append(make_signal_record(
                date_key(dt), execution_date, "BUY" if current_state else "SELL", execution_price, row
            ))
        previous_state = current_state

    return events


def simulate_full_alignment_strategy(
    work: pd.DataFrame,
    previous_state: bool | None = None,
    transaction_tax_sell: float = 0.0,
) -> dict[str, Any]:
    """1d > 5d > 20d > 200d 정배열 전략을 최근 구간에서 시뮬레이션한다.

    전환 신호를 확정한 다음 거래일의 1일 VWAP proxy 가격으로 체결한다.
    최근 구간 시작 전 포지션은 이월하지 않는다.
    반환값은 JSON 직렬화 가능한 dict로 유지해 trend/detail 생성 로직에서 공유한다.
    """
    cash = 1.0
    shares = 0.0
    in_position = False
    entry_price: float | None = None
    entry_date: str | None = None
    last_signal = "WAIT"
    last_signal_date: str | None = None
    trades: list[dict[str, Any]] = []
    signals = build_full_alignment_events(work, previous_state=previous_state)
    executions = {event["execution_date"]: event for event in signals if event.get("execution_date")}
    equity_curve: list[float] = []
    position_days = 0

    for i in range(len(work)):
        row = work.iloc[i]
        valuation_price = float(row["vwap_1d"])

        execution_dt = date_key(work.index[i])
        event = executions.get(execution_dt)
        if event:
            signal = event["type"]
            last_signal = signal
            last_signal_date = event["date"]
            if not in_position and signal == "BUY":
                shares = cash * (1 - STRATEGY_FEE_ONE_WAY) / valuation_price
                cash = 0.0
                in_position = True
                entry_price = valuation_price
                entry_date = execution_dt
            elif in_position and signal == "SELL":
                assert entry_price is not None
                exit_price = valuation_price
                cash = shares * exit_price * (
                    1 - STRATEGY_FEE_ONE_WAY - transaction_tax_sell
                )
                shares = 0.0
                in_position = False
                ret = (
                    (exit_price / entry_price)
                    * (1 - STRATEGY_FEE_ONE_WAY)
                    * (1 - STRATEGY_FEE_ONE_WAY - transaction_tax_sell)
                    - 1
                ) * 100
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": execution_dt,
                    "entry_price": safe_round(entry_price),
                    "exit_price": round(exit_price, 4),
                    "return_pct": safe_round(ret, 2),
                })
                entry_price = None
                entry_date = None

        if in_position:
            position_days += 1
        equity_curve.append(shares * valuation_price if in_position else cash)

    final_price = float(work["vwap_1d"].iloc[-1]) if len(work) else 0.0
    final_equity = shares * final_price if in_position else cash
    return {
        "cash": cash,
        "shares": shares,
        "in_position": in_position,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "last_signal": last_signal,
        "last_signal_date": last_signal_date,
        "trades": trades,
        "signals": signals,
        "equity_curve": equity_curve,
        "position_days": position_days,
        "final_equity": final_equity,
    }


def simulate_volatility_breakout_strategy(
    context: pd.DataFrame,
    visible_days: int = LOOKBACK_TRADING_DAYS,
    k: float = VOLATILITY_BREAKOUT_K,
    transaction_tax_sell: float = 0.0,
) -> dict[str, Any]:
    """전일 변동폭 기반 돌파 매수 후 다음 거래일 시가에 청산한다.

    돌파가는 `당일 시가 + (전일 고가 - 전일 저가) * k`다. 최근 표시
    구간의 첫날은 직전 한 행을 돌파가 계산에만 사용하고, 마지막 날은 다음
    거래일 시가가 없으므로 신규 진입하지 않는다. 매 거래마다 전액을
    재투자하고 매수·매도 양쪽에 동일한 편도 수수료를 적용한다.
    """
    cash = 1.0
    trades = 0
    journal: list[dict[str, Any]] = []
    visible_days = max(1, int(visible_days))
    first_visible_index = max(0, len(context) - visible_days)

    for i in range(max(1, first_visible_index), len(context) - 1):
        previous = context.iloc[i - 1]
        today = context.iloc[i]
        next_day = context.iloc[i + 1]
        values = [
            previous.get("high"),
            previous.get("low"),
            today.get("open"),
            today.get("high"),
            next_day.get("open"),
        ]
        if any(is_missing(value) for value in values):
            continue

        previous_range = float(previous["high"]) - float(previous["low"])
        if previous_range <= 0:
            continue

        target_price = float(today["open"]) + previous_range * float(k)
        exit_price = float(next_day["open"])
        if target_price <= 0 or exit_price <= 0 or float(today["high"]) < target_price:
            continue

        shares = cash * (1 - STRATEGY_FEE_ONE_WAY) / target_price
        cash = shares * exit_price * (
            1 - STRATEGY_FEE_ONE_WAY - transaction_tax_sell
        )
        trades += 1
        trade_return = (
            (exit_price / target_price)
            * (1 - STRATEGY_FEE_ONE_WAY)
            * (1 - STRATEGY_FEE_ONE_WAY - transaction_tax_sell)
            - 1
        ) * 100
        journal.append({
            "entry_date": date_key(context.index[i]),
            "entry_price": safe_round(target_price),
            "exit_date": date_key(context.index[i + 1]),
            "exit_price": safe_round(exit_price),
            "return_pct": safe_round(trade_return, 2),
            "status": "CLOSED",
        })

    return {
        "k": float(k),
        "trades": trades,
        "journal": journal,
        "final_equity": cash,
        "strategy_return_pct": (cash - 1) * 100,
    }


def build_full_alignment_journal(
    work: pd.DataFrame,
    simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    """완료 거래와 현재 보유 포지션을 공통 일지 형식으로 직렬화한다."""
    journal: list[dict[str, Any]] = []
    for trade in simulation["trades"]:
        holding_days = len(
            work.loc[pd.Timestamp(trade["entry_date"]):pd.Timestamp(trade["exit_date"])]
        )
        journal.append({
            "entry_date": trade["entry_date"],
            "entry_price": trade["entry_price"],
            "exit_date": trade["exit_date"],
            "exit_price": trade["exit_price"],
            "return_pct": trade["return_pct"],
            "holding_days": holding_days,
            "status": "CLOSED",
        })

    if simulation["in_position"] and simulation["entry_date"] and simulation["entry_price"]:
        valuation_date = date_key(work.index[-1])
        valuation_price = float(work["vwap_1d"].iloc[-1])
        current_return = (
            valuation_price
            / float(simulation["entry_price"])
            * (1 - STRATEGY_FEE_ONE_WAY)
            - 1
        ) * 100
        journal.append({
            "entry_date": simulation["entry_date"],
            "entry_price": safe_round(simulation["entry_price"]),
            "exit_date": None,
            "exit_price": None,
            "valuation_date": valuation_date,
            "valuation_price": safe_round(valuation_price),
            "return_pct": safe_round(current_return, 2),
            "holding_days": len(work.loc[pd.Timestamp(simulation["entry_date"]):]),
            "status": "OPEN",
        })

    return journal


def calc_trade_holding_stats(trades: list[dict[str, Any]], work: pd.DataFrame) -> tuple[float | None, int | None]:
    hold_lengths: list[int] = []
    for trade in trades:
        if trade.get("entry_date") and trade.get("exit_date"):
            hold_lengths.append(len(work.loc[pd.Timestamp(trade["entry_date"]):pd.Timestamp(trade["exit_date"])]))
    if not hold_lengths:
        return None, None
    return sum(hold_lengths) / len(hold_lengths), max(hold_lengths)


def build_latest_strategy_snapshot(
    work: pd.DataFrame,
    simulation: dict[str, Any],
) -> dict[str, Any]:
    """최신 거래일의 정배열 상태와 현재 포지션을 직렬화한다."""
    latest = work.iloc[-1]
    current_signal = full_alignment_signal(
        latest["vwap_1d"],
        latest["vwap_5d"],
        latest["vwap_20d"],
        latest["vwap_200d"],
    )
    alignment = {
        "WAIT": "N/A",
        "BUY": "1 > 5 > 20 > 200",
        "SELL": "정배열 아님",
    }[current_signal]
    action = {"WAIT": "대기", "BUY": "매수", "SELL": "매도"}[current_signal]

    current_trade_return = None
    if simulation["in_position"] and simulation["entry_price"]:
        current_trade_return = (
            float(work["vwap_1d"].iloc[-1])
            / simulation["entry_price"]
            * (1 - STRATEGY_FEE_ONE_WAY)
            - 1
        ) * 100

    holding_days = None
    if simulation["in_position"] and simulation["entry_date"]:
        holding_days = len(work.loc[pd.Timestamp(simulation["entry_date"]):])

    return {
        "date": date_key(work.index[-1]),
        "vwap1": safe_round(latest["vwap_1d"]),
        "vwap5": safe_round(latest["vwap_5d"]),
        "vwap20": safe_round(latest["vwap_20d"]),
        "vwap200": safe_round(latest["vwap_200d"]),
        "signal": current_signal,
        "alignment": alignment,
        "in_position": simulation["in_position"],
        "action": action,
        "last_signal": simulation["last_signal"],
        "last_signal_date": simulation["last_signal_date"],
        "holding_days": holding_days,
        "entry_date": simulation["entry_date"],
        "entry_price": safe_round(simulation["entry_price"]),
        "current_trade_return_pct": safe_round(current_trade_return, 2),
    }


def build_backtest_summary(
    work: pd.DataFrame,
    simulation: dict[str, Any],
    volatility_breakout: dict[str, Any],
) -> dict[str, Any]:
    """최근 표시 구간의 전략·단순보유 수익률과 거래 통계를 요약한다."""
    trades = simulation["trades"]
    wins = [trade for trade in trades if trade.get("return_pct") is not None and trade["return_pct"] > 0]
    avg_holding_days, max_holding_days = calc_trade_holding_stats(trades, work)
    strategy_return = (simulation["final_equity"] - 1) * 100
    buy_hold_return = pct_change(
        float(work["vwap_1d"].iloc[0]),
        float(work["vwap_1d"].iloc[-1]),
    )
    strategy_return = safe_round(strategy_return, 2)
    buy_hold_return = safe_round(buy_hold_return, 2)
    volatility_breakout_return = safe_round(volatility_breakout["strategy_return_pct"], 2)
    volatility_breakout_wins = [
        trade for trade in volatility_breakout["journal"]
        if trade.get("return_pct") is not None and trade["return_pct"] > 0
    ]

    return {
        "period": f"recent_{LOOKBACK_TRADING_DAYS}_trading_days",
        "start_date": date_key(work.index[0]),
        "end_date": date_key(work.index[-1]),
        "strategy_return_pct": strategy_return,
        "buy_hold_return_pct": buy_hold_return,
        "trades": len(trades),
        "win_rate_pct": safe_round(len(wins) / len(trades) * 100 if trades else None, 2),
        "exposure_pct": safe_round(simulation["position_days"] / len(work) * 100 if len(work) else None, 2),
        "avg_holding_days": safe_round(avg_holding_days, 1),
        "max_holding_days": max_holding_days,
        "volatility_breakout": {
            "k": volatility_breakout["k"],
            "trades": volatility_breakout["trades"],
            "win_rate_pct": safe_round(
                len(volatility_breakout_wins) / volatility_breakout["trades"] * 100
                if volatility_breakout["trades"] else None,
                2,
            ),
            "entry": "today_open + previous_range * k",
            "exit": "next_day_open",
            "fee_one_way_pct": STRATEGY_RULES["fee_one_way_pct"],
            "final_day_entry": "skipped_without_next_open",
        },
        "rolling_200d": {
            "window_days": len(work),
            "strategy_return_pct": strategy_return,
            "buy_hold_return_pct": buy_hold_return,
            "volatility_breakout_return_pct": volatility_breakout_return,
        },
    }


def build_strategy_signal(df: pd.DataFrame, ticker: str | None = None) -> dict[str, Any]:
    """최근 200거래일 기준 1d/5d/20d/200d 정배열 전략 요약.

    신호: 당일 종가 확정 후 판단. 백테스트 체결: 신호 다음 거래일 1일 VWAP proxy, 편도 수수료 0.03%.
    """
    cost_model = build_strategy_cost_model(ticker)
    if len(df) < MIN_STRATEGY_TRADING_DAYS:
        return {
            "available": False,
            "reason": "insufficient_recent_history",
            "cost_model": cost_model,
        }

    context = prepare_strategy_frame(df, LOOKBACK_TRADING_DAYS + 1)
    work = context.tail(LOOKBACK_TRADING_DAYS).copy()
    previous_state = alignment_state(context.iloc[-len(work) - 1]) if len(context) > len(work) else None
    transaction_tax_sell = cost_model["transaction_tax_sell_pct"] / 100
    simulation = simulate_full_alignment_strategy(
        work,
        previous_state=previous_state,
        transaction_tax_sell=transaction_tax_sell,
    )
    volatility_breakout = simulate_volatility_breakout_strategy(
        context,
        visible_days=len(work),
        transaction_tax_sell=transaction_tax_sell,
    )

    return {
        "available": True,
        "strategy": "VWAP 1/5/20/200 full alignment",
        "rules": dict(STRATEGY_RULES),
        "cost_model": cost_model,
        "latest": build_latest_strategy_snapshot(work, simulation),
        "backtest": build_backtest_summary(work, simulation, volatility_breakout),
        "backtest_journals": {
            "volatility_breakout": volatility_breakout["journal"],
            "full_alignment": build_full_alignment_journal(work, simulation),
        },
        "signals": simulation["signals"],
    }


# ──────────────────────────────────────────────────────────
# 종목별 데이터 처리
# ──────────────────────────────────────────────────────────
def fetch_naver_daily_ohlcv(symbol: str, target_date: date) -> dict[str, Any] | None:
    """Naver siseJson daily endpoint에서 KRX 당일 OHLCV 한 건을 가져온다."""
    ymd = target_date.strftime("%Y%m%d")
    url = "https://api.finance.naver.com/siseJson.naver"
    params = {
        "symbol": symbol,
        "requestType": "1",
        "startTime": ymd,
        "endTime": ymd,
        "timeframe": "day",
    }
    resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    resp.raise_for_status()

    rows: list[list[Any]] = []
    for match in re.finditer(r"\[[^\[\]]+\]", resp.text):
        try:
            row = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            continue
        if isinstance(row, list) and row and str(row[0]).isdigit():
            rows.append(row)

    if not rows:
        return None

    row = rows[-1]
    if str(row[0]) != ymd:
        return None
    return {
        "date": target_date,
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": int(row[5]),
    }


def maybe_patch_krx_today(
    df: pd.DataFrame,
    ticker: str,
    today: date,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """당일 KRX 행은 Naver 일봉으로 보강/덮어쓴다.

    Yahoo/yfinance는 장 마감 직후 같은 날짜 행을 주더라도 KRX ETF/종목의
    OHLCV가 공식 Naver 일봉과 다른 경우가 있다. 한국 장 마감 후 수동 갱신은
    당일 체결을 반영하는 용도이므로, KRX 티커는 Naver 당일 행이 있으면 기존
    같은 날짜 행까지 덮어써서 오늘자 계산 기준을 공식 일봉에 맞춘다.

    단, 오전 catch-up 실행처럼 한국장이 아직 진행 중이면 Naver 일봉도
    미확정 장중 값이므로 당일 보강을 하지 않는다.
    """
    if not (ticker.endswith(".KS") or ticker.endswith(".KQ")):
        return df
    if df.empty:
        return df

    now_kst = now.astimezone(KST) if now is not None else datetime.now(KST)
    if today == now_kst.date() and now_kst.time() < KRX_TODAY_PATCH_AFTER:
        return df

    symbol = ticker.split(".", 1)[0]
    latest_date: date = cast(date, pd.Timestamp(cast(Any, df.index[-1])).date())
    if latest_date > today:
        return df

    try:
        today_row = fetch_naver_daily_ohlcv(symbol, today)
    except Exception as e:
        print(f"    [WARN] {ticker}: Naver 당일 데이터 보강 실패: {e}")
        return df
    if today_row is None:
        return df

    patched = df.copy()
    patched.loc[pd.Timestamp(today_row["date"]), ["open", "high", "low", "close", "volume"]] = [
        today_row["open"], today_row["high"], today_row["low"], today_row["close"], today_row["volume"]
    ]
    patched = patched.sort_index().tail(HISTORY_TRADING_DAYS).copy()
    patched.attrs["krx_today_patched"] = True
    patched.attrs["krx_today_source"] = "naver_siseJson"
    patched.attrs["krx_today_date"] = today.isoformat()
    return patched


def download_ohlcv(ticker: str, end_date: str) -> pd.DataFrame:
    """최근 200일 백테스트와 VWAP200 warm-up에 필요한 OHLCV를 다운로드한다."""
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=DOWNLOAD_CALENDAR_DAYS)).strftime("%Y-%m-%d")
    # yfinance의 end는 배타적이라 다음 날짜를 넘겨준다. 그래도 KRX 당일이 없으면 Naver로 보강한다.
    yf_end_date = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(
        ticker,
        start=start_date,
        end=yf_end_date,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    raw.columns = [c[0].lower() for c in raw.columns]
    df = raw[["open", "high", "low", "close", "volume"]].dropna().tail(HISTORY_TRADING_DAYS).copy()
    return maybe_patch_krx_today(df, ticker, end_dt.date())


def build_vwap_structure(df: pd.DataFrame) -> tuple[list[dict[str, Any]], float | None]:
    """VWAP 기간 구조 스냅샷 생성. (structure_list, base_vwap) 반환."""
    structure: list[dict[str, Any]] = []
    base_vwap: float | None = None

    for w in WINDOWS:
        if len(df) >= w:
            v = compute_vwap(df.iloc[-w:])
            if w == 200:
                base_vwap = v
            structure.append({"window": w, "vwap": round(v, 4)})
        else:
            structure.append({"window": w, "vwap": None})

    if base_vwap:
        for item in structure:
            if item["vwap"] is not None:
                item["norm"] = round(item["vwap"] / base_vwap * 100, 2)
            else:
                item["norm"] = None

    return structure, base_vwap


def build_recent_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """최근 200거래일 close 기반 미니 레코드. 현재 UI에서는 보조/호환 필드다."""
    return [
        {"date": date_key(dt), "price": round(float(row["close"]), 2)}
        for dt, row in df.tail(LOOKBACK_TRADING_DAYS).iterrows()
    ]


def build_detail_data(
    name: str,
    ticker: str,
    df: pd.DataFrame,
    strategy_signal: dict[str, Any] | None = None,
    backtest_journals: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """상세 데이터 생성: 최근 200거래일, VWAP line/Volume Profile은 1/5/20/200d만 표시."""
    if strategy_signal is None:
        strategy_payload = build_strategy_signal(df, ticker=ticker)
        if backtest_journals is None:
            backtest_journals = strategy_payload.get("backtest_journals")
        strategy_signal = {
            key: value for key, value in strategy_payload.items()
            if key != "backtest_journals"
        }

    work = prepare_strategy_frame(df)
    ohlcv = []
    for _i, (dt, row) in enumerate(work.iterrows()):
        rec: dict[str, Any] = {
            "date": date_key(dt),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "volume": int(row["volume"]),
            "vwap_1d": safe_round(row["vwap_1d"]),
        }
        for window in WINDOWS:
            rec[f"vwap_{window}d"] = safe_round(row[f"vwap_{window}d"])
        ohlcv.append(rec)

    volume_profile: dict[str, Any] = {}
    for period in VOLUME_PROFILE_WINDOWS:
        if len(work) >= period:
            vwap_val, buckets = compute_vwap_with_profile(work.iloc[-period:])
            volume_profile[f"{period}d"] = {
                "buckets": buckets,
                "vwap": round(vwap_val, 4),
            }

    return {
        "name": name,
        "ticker": ticker,
        "ohlcv": ohlcv,
        "volume_profile": volume_profile,
        "strategy_signal": strategy_signal if strategy_signal is not None else build_strategy_signal(df, ticker=ticker),
        "backtest_journals": backtest_journals or {
            "volatility_breakout": [],
            "full_alignment": [],
        },
        "lookback_trading_days": LOOKBACK_TRADING_DAYS,
        "latest_price": round(float(df["close"].iloc[-1]), 2),
    }


def attach_krx_data_source(target: dict[str, Any], df: pd.DataFrame) -> None:
    """Naver 당일 보강 이력을 trend 메타데이터에 일관되게 부착."""
    if df.attrs.get("krx_today_patched"):
        target["data_source"] = {
            "latest_krx_daily": df.attrs.get("krx_today_source"),
            "latest_krx_date": df.attrs.get("krx_today_date"),
        }


def build_detail_meta(run_time: str, asset_result: dict[str, Any]) -> dict[str, Any]:
    """detail_data의 기존 _meta KRX 키 계약을 보존한다."""
    meta: dict[str, Any] = {"updated_at": run_time}
    data_source = asset_result.get("data_source")
    if data_source:
        # Preserve the historical detail _meta contract while sourcing the
        # values from the shared OHLCV snapshot metadata used for trend.
        meta.update({
            "krx_today_source": data_source.get("latest_krx_daily"),
            "krx_today_date": data_source.get("latest_krx_date"),
        })
    return meta


def build_asset_outputs(name: str, ticker: str, df: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """동일한 OHLCV 스냅샷에서 trend/detail 결과를 함께 생성한다."""
    df = df.tail(HISTORY_TRADING_DAYS).copy()
    vwap_structure, _ = build_vwap_structure(df)
    records = build_recent_records(df)
    strategy_payload = build_strategy_signal(df, ticker=ticker)
    backtest_journals = strategy_payload.get("backtest_journals", {
        "volatility_breakout": [],
        "full_alignment": [],
    })
    strategy_signal = {
        key: value for key, value in strategy_payload.items()
        if key != "backtest_journals"
    }

    asset_result = {
        "ticker": ticker,
        "records": records,
        "vwap_structure": vwap_structure,
        "strategy_signal": strategy_signal,
        "lookback_trading_days": LOOKBACK_TRADING_DAYS,
        "latest_price": round(float(df["close"].iloc[-1]), 2),
    }
    attach_krx_data_source(asset_result, df)
    detail_result = build_detail_data(
        name,
        ticker,
        df,
        strategy_signal=strategy_signal,
        backtest_journals=backtest_journals,
    )
    return asset_result, detail_result


def process_asset(
    name: str, ticker: str, end_date: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """단일 종목 처리. 다운로드는 한 번만 수행하고 trend/detail을 함께 반환한다."""
    print(f"  {name} ({ticker})...")
    try:
        df = download_ohlcv(ticker, end_date)
    except Exception as e:
        print(f"    [ERROR] {name}: {e}")
        return None

    if df.empty:
        print(f"    [WARN] {name}: 데이터 없음")
        return None

    asset_result, detail_result = build_asset_outputs(name, ticker, df)
    s = {item["window"]: item for item in asset_result["vwap_structure"]}
    print(f"    5/200={s.get(5, {}).get('norm')} / 20/200={s.get(20, {}).get('norm')}")
    return asset_result, detail_result


def remove_unregistered_detail_files() -> list[str]:
    """등록 목록에서 제거된 종목의 오래된 상세 JSON을 삭제한다."""
    os.makedirs(DETAIL_DIR, exist_ok=True)
    registered_tickers = {ticker for _, ticker in ASSETS}
    removed: list[str] = []
    for filename in os.listdir(DETAIL_DIR):
        if not filename.endswith(".json"):
            continue
        ticker = filename[:-5]
        if ticker in registered_tickers:
            continue
        os.remove(os.path.join(DETAIL_DIR, filename))
        removed.append(ticker)
    return sorted(removed)


def collect_asset_outputs(
    run_time: str,
    end_date: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    """등록 종목을 처리해 trend/detail 결과와 실패 종목을 수집한다."""
    result: dict[str, Any] = {
        "_meta": {
            "updated_at": run_time,
            "lookback_trading_days": LOOKBACK_TRADING_DAYS,
        }
    }
    detail_results: dict[str, dict[str, Any]] = {}
    failed: list[str] = []

    for name, ticker in ASSETS:
        outputs = process_asset(name, ticker, end_date)
        if outputs is None:
            failed.append(name)
            continue
        asset_data, detail_data = outputs
        result[name] = asset_data
        detail_results[ticker] = detail_data

    return result, detail_results, failed


def attach_run_krx_metadata(result: dict[str, Any], end_date: str) -> None:
    """Naver 당일 보강 현황을 trend 최상위 메타에 요약한다."""
    patched_count = sum(
        1
        for name, data in result.items()
        if not name.startswith("_")
        and isinstance(data, dict)
        and data.get("data_source", {}).get("latest_krx_daily") == "naver_siseJson"
    )
    if patched_count:
        result["_meta"].update({
            "krx_today_source": "naver_siseJson",
            "krx_today_date": end_date,
            "krx_today_patched_count": patched_count,
        })


def write_json_file(path: str, payload: dict[str, Any]) -> None:
    """브라우저에서 파싱 가능한 strict JSON으로 저장한다."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, allow_nan=False)


def write_detail_files(
    run_time: str,
    result: dict[str, Any],
    detail_results: dict[str, dict[str, Any]],
    failed: list[str],
) -> None:
    """stale 상세 파일을 정리하고 성공한 종목의 상세 결과를 저장한다."""
    removed_tickers = remove_unregistered_detail_files()
    if removed_tickers:
        print(f"\n🗑️ 미등록 상세 데이터 삭제: {', '.join(removed_tickers)}")

    print("\n📊 detail_data 생성 중...")
    for name, ticker in ASSETS:
        if name in failed or ticker not in detail_results:
            continue
        try:
            detail = detail_results[ticker]
            detail["_meta"] = build_detail_meta(run_time, result.get(name, {}))
            out_path = os.path.join(DETAIL_DIR, f"{ticker}.json")
            write_json_file(out_path, detail)
            print(f"  ✅ {name} → {out_path}")
        except Exception as error:
            print(f"  [ERROR] detail {name}: {error}")


# ──────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────
def main() -> None:
    now = datetime.now(KST)
    run_time = now.strftime("%Y-%m-%d %H:%M")
    end_date = now.strftime("%Y-%m-%d")

    result, detail_results, failed = collect_asset_outputs(run_time, end_date)
    attach_run_krx_metadata(result, end_date)
    write_json_file(OUTPUT_PATH, result)
    write_detail_files(run_time, result, detail_results, failed)

    print(f"\n✅ 저장 완료: {OUTPUT_PATH}  (기준: {run_time})")
    if failed:
        print(f"⚠️  실패 종목: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
