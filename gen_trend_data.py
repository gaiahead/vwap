"""VWAP 추세 데이터 생성기.

yfinance에서 주가 데이터를 받아 정규분포 기반 Volume Profile VWAP를 계산하고,
trend_data.json으로 출력한다.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

# ──────────────────────────────────────────────────────────
# 종목 설정
# ──────────────────────────────────────────────────────────
AssetTuple = tuple[str, str, str]  # (표시명, 티커, 그룹)

ASSETS: list[AssetTuple] = [
    # 그룹 1: 핵심 매크로 / 시장 폭 / 크레딧
    ("TLT",                        "TLT",       "g1"),
    ("GLD",                        "GLD",       "g1"),
    ("IBIT",                       "IBIT",      "g1"),
    ("SPY",                        "SPY",       "g1"),
    ("QQQ",                        "QQQ",       "g1"),
    ("SCHD",                       "SCHD",      "g1"),
    ("XLE",                        "XLE",       "g1"),
    ("GUNR",                       "GUNR",      "g1"),
    ("IXC",                        "IXC",       "g1"),  # 글로벌 에너지
    ("XOP",                        "XOP",       "g1"),  # 미국 석유·가스 E&P
    ("OIH",                        "OIH",       "g1"),  # 오일서비스
    ("Exxon Mobil",                "XOM",       "g1"),
    ("Shell",                      "SHEL",      "g1"),
    ("SLB",                        "SLB",       "g1"),
    ("RSP",                        "RSP",       "g1"),  # S&P500 동일가중
    ("IWM",                        "IWM",       "g1"),  # 러셀2000
    ("IEF",                        "IEF",       "g1"),  # 미국 7-10년 국채
    ("SHY",                        "SHY",       "g1"),  # 미국 단기국채
    ("TIP",                        "TIP",       "g1"),  # 물가연동채
    ("HYG",                        "HYG",       "g1"),  # 하이일드 채권
    ("LQD",                        "LQD",       "g1"),  # 투자등급 회사채
    ("UUP",                        "UUP",       "g1"),  # 달러 인덱스 ETF
    ("FXY",                        "FXY",       "g1"),  # 엔화 ETF

    # 그룹 2: 미국 섹터 / 원자재 / 글로벌 지역
    ("XLK",                        "XLK",       "g2"),  # 기술
    ("ITA",                        "ITA",       "g2"),  # 미국 대형 방산 ETF
    ("XAR",                        "XAR",       "g2"),  # 미국 중소형 방산 ETF
    ("Lockheed Martin",            "LMT",       "g2"),
    ("RTX",                        "RTX",       "g2"),
    ("Rheinmetall",                "RHM.DE",    "g2"),
    ("BAE Systems",                "BA.L",      "g2"),
    ("Saab",                       "SAAB-B.ST", "g2"),
    ("XLF",                        "XLF",       "g2"),  # 금융
    ("XLV",                        "XLV",       "g2"),  # 헬스케어
    ("XLI",                        "XLI",       "g2"),  # 산업재
    ("XLY",                        "XLY",       "g2"),  # 경기소비재
    ("XLP",                        "XLP",       "g2"),  # 필수소비재
    ("XLU",                        "XLU",       "g2"),  # 유틸리티
    ("XLRE",                       "XLRE",      "g2"),  # 부동산
    ("XLB",                        "XLB",       "g2"),  # 소재
    ("USO",                        "USO",       "g2"),  # 원유
    ("CPER",                       "CPER",      "g2"),  # 구리
    ("COPX",                       "COPX",      "g2"),  # 구리 광산
    ("DBA",                        "DBA",       "g2"),  # 농산물
    ("URA",                        "URA",       "g2"),  # 우라늄/원전
    ("SLV",                        "SLV",       "g2"),  # 은
    ("EFA",                        "EFA",       "g2"),  # 선진국 ex-US
    ("EEM",                        "EEM",       "g2"),  # 신흥국
    ("EWJ",                        "EWJ",       "g2"),  # 일본
    ("FXI",                        "FXI",       "g2"),  # 중국 대형주
    ("INDA",                       "INDA",      "g2"),  # 인도
    ("EWT",                        "EWT",       "g2"),  # 대만

    # 그룹 3: 미국/글로벌 AI·기술주와 관련 ETF
    ("SOL 미국테크TOP10",            "481190.KS", "g3"),
    ("TIGER 미국필라델피아반도체나스닥", "381180.KS", "g3"),
    ("KODEX 미국반도체",              "390390.KS", "g3"),
    ("ACE 글로벌반도체TOP4 Plus",     "446770.KS", "g3"),
    ("엔비디아",                      "NVDA",      "g3"),
    ("알파벳",                        "GOOGL",     "g3"),
    ("애플",                          "AAPL",      "g3"),
    ("마이크로소프트",                 "MSFT",      "g3"),
    ("아마존",                        "AMZN",      "g3"),
    ("메타",                          "META",      "g3"),
    ("브로드컴",                      "AVGO",      "g3"),
    ("테슬라",                        "TSLA",      "g3"),
    ("넷플릭스",                      "NFLX",      "g3"),
    ("팔란티어",                      "PLTR",      "g3"),
    ("시스코",                        "CSCO",      "g3"),

    # 그룹 4: 한국 대표지수 / 반도체
    ("KODEX 200",                    "069500.KS", "g4"),
    ("KODEX 코스닥150",               "229200.KS", "g4"),
    ("KODEX 반도체",                  "091160.KS", "g4"),
    ("KODEX AI반도체",                "395160.KS", "g4"),
    ("KODEX AI반도체핵심장비",          "471990.KS", "g4"),
    ("TIGER 반도체TOP10",             "396500.KS", "g4"),
    ("삼성전자",                      "005930.KS", "g4"),
    ("SK하이닉스",                    "000660.KS", "g4"),
    ("한미반도체",                    "042700.KS", "g4"),
    ("리노공업",                      "058470.KS", "g4"),

    # 그룹 5: 한국 주요 섹터 / 테마
    ("PLUS 태양광&ESS",              "389260.KS", "g5"),
    ("한화솔루션",                    "009830.KS", "g5"),
    ("OCI홀딩스",                    "010060.KS", "g5"),
    ("HD현대에너지솔루션",              "322000.KS", "g5"),
    ("씨에스윈드",                    "112610.KS", "g5"),
    ("씨에스베어링",                  "297090.KQ", "g5"),
    ("SK이터닉스",                   "475150.KS", "g5"),
    ("KODEX 자동차",                  "091180.KS", "g5"),
    ("KODEX 은행",                    "091170.KS", "g5"),
    ("KODEX 2차전지산업",              "305720.KS", "g5"),
    ("KODEX 헬스케어",                "266420.KS", "g5"),
    ("KODEX 조선TOP10",               "0115D0.KS", "g5"),
    ("HD현대중공업",                   "329180.KS", "g5"),
    ("삼성중공업",                     "010140.KS", "g5"),
    ("한화오션",                       "042660.KS", "g5"),
    ("KODEX 방산TOP10",               "0080G0.KS", "g5"),
    ("한화에어로스페이스",              "012450.KS", "g5"),
    ("현대로템",                       "064350.KS", "g5"),
    ("LIG디펜스&에어로스페이스",       "079550.KS", "g5"),
    ("한국항공우주",                    "047810.KS", "g5"),
    ("한화시스템",                    "272210.KS", "g5"),
    ("풍산",                          "103140.KS", "g5"),
    ("휴니드",                        "005870.KS", "g5"),
    ("KODEX 금융고배당TOP10",          "498410.KS", "g5"),
    ("TIGER 소프트웨어",               "157490.KS", "g5"),
    ("KODEX IT",                      "266370.KS", "g5"),
    ("TIGER 미디어컨텐츠",             "228810.KS", "g5"),
    ("KODEX 로봇액티브",               "445290.KS", "g5"),
]
WINDOWS: list[int] = list(range(10, 201, 10))  # 10~200, 10일 간격
N_BUCKETS: int = 20
KST: timezone = timezone(timedelta(hours=9))
DATA_START: str = "2020-01-01"
WEEKLY_CUTOFF: date = date(2025, 1, 6)
EXCLUDE_DATES: frozenset[str] = frozenset({"2025-12-31", "2025-12-30", "2025-12-29"})
OUTPUT_PATH: str = "trend_data.json"
DETAIL_DIR: str = "detail_data"


# ──────────────────────────────────────────────────────────
# VWAP 계산
# ──────────────────────────────────────────────────────────
def compute_vwap(df_window: pd.DataFrame) -> float:
    """정규분포 기반 Volume Profile VWAP."""
    lo = float(df_window["low"].min())
    hi = float(df_window["high"].max())
    if hi == lo:
        return float(df_window["close"].mean())

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
        return float(df_window["close"].iloc[-1])
    return float((bucket_prices * bvol).sum() / total_vol)


def compute_vwap_with_profile(
    df_window: pd.DataFrame,
) -> tuple[float, list[dict[str, float]]]:
    """정규분포 기반 Volume Profile VWAP + 버킷 배열 반환."""
    lo = float(df_window["low"].min())
    hi = float(df_window["high"].max())
    if hi == lo:
        mid = float(df_window["close"].mean())
        bsize = 1.0
        bucket_prices = [mid] * N_BUCKETS
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


def compute_vwap_series(df: pd.DataFrame, window: int = 20) -> list[float | None]:
    """롤링 윈도우 VWAP 시계열. 현재 봉 포함 (i-window+1 : i+1)."""
    vwaps: list[float | None] = []
    for i in range(len(df)):
        if i < window - 1:
            vwaps.append(None)
            continue
        vwaps.append(compute_vwap(df.iloc[i - window + 1 : i + 1]))
    return vwaps


def compute_proxy_vwap_series(df: pd.DataFrame, window: int) -> list[float | None]:
    """백테스트/전략 신호용 빠른 일봉 VWAP proxy.

    대표가격 = (High + Low + Close) / 3, n일 VWAP = Σ(대표가격×거래량)/Σ거래량.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    denom = df["volume"].rolling(window).sum()
    series = pv.rolling(window).sum() / denom
    return [None if pd.isna(v) else float(v) for v in series.tolist()]


def strength_score(arr: list[float | None], norm_window: int = 52) -> list[float | None]:
    """백분위 기반 강도 점수 (-100 ~ +100)."""
    scores: list[float | None] = []
    for i in range(len(arr)):
        v = arr[i]
        if v is None or (isinstance(v, float) and np.isnan(v)):
            scores.append(None)
            continue
        window_vals = [
            x
            for x in arr[max(0, i - norm_window) : i + 1]
            if x is not None and not (isinstance(x, float) and np.isnan(x))
        ]
        if len(window_vals) < 5:
            scores.append(None)
            continue
        pct = sum(1 for x in window_vals if x <= v) / len(window_vals)
        scores.append(round((pct * 2 - 1) * 100, 1))
    return scores


def safe_round(value: float | None, digits: int = 4) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), digits)


def pct_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return (end / start - 1) * 100


def calc_max_drawdown(equity: list[float]) -> float | None:
    if not equity:
        return None
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, value / peak - 1)
    return max_dd * 100


def build_strategy_signal(df: pd.DataFrame) -> dict[str, Any]:
    """공통 VWAP 10/20/40 전략 상태와 간단 백테스트 요약.

    신호: 당일 종가 확정 후 판단. 백테스트 체결: 다음 거래일 시가, 편도 수수료 0.03%.
    """
    if len(df) < 45:
        return {"available": False, "reason": "insufficient_history"}

    work = df.copy()
    work["vwap_10d"] = compute_proxy_vwap_series(work, 10)
    work["vwap_20d"] = compute_proxy_vwap_series(work, 20)
    work["vwap_40d"] = compute_proxy_vwap_series(work, 40)

    fee = 0.0003
    cash = 1.0
    shares = 0.0
    in_position = False
    entry_price: float | None = None
    entry_date: str | None = None
    last_signal = "WAIT"
    last_signal_date: str | None = None
    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    equity_curve: list[float] = []

    for i in range(len(work)):
        row = work.iloc[i]
        current_close = float(row["close"])
        equity_curve.append(shares * current_close if in_position else cash)
        if i >= len(work) - 1:
            continue

        v10, v20, v40 = row["vwap_10d"], row["vwap_20d"], row["vwap_40d"]
        if pd.isna(v10) or pd.isna(v20) or pd.isna(v40):
            continue

        dt = str(work.index[i].date())
        next_dt = str(work.index[i + 1].date())
        next_open = float(work.iloc[i + 1]["open"])
        buy_cond = float(v10) > float(v20) > float(v40)
        sell_cond = float(v10) < float(v20)

        if not in_position and buy_cond:
            shares = cash * (1 - fee) / next_open
            cash = 0.0
            in_position = True
            entry_price = next_open
            entry_date = next_dt
            last_signal = "BUY"
            last_signal_date = dt
            signals.append({"date": dt, "execution_date": next_dt, "type": "BUY", "price": round(next_open, 4)})
        elif in_position and sell_cond:
            exit_price = next_open
            cash = shares * exit_price * (1 - fee)
            shares = 0.0
            in_position = False
            last_signal = "SELL"
            last_signal_date = dt
            ret = pct_change(entry_price, exit_price) if entry_price is not None else None
            trades.append({
                "entry_date": entry_date,
                "exit_date": next_dt,
                "entry_price": safe_round(entry_price),
                "exit_price": round(exit_price, 4),
                "return_pct": safe_round(ret, 2),
            })
            signals.append({"date": dt, "execution_date": next_dt, "type": "SELL", "price": round(exit_price, 4)})
            entry_price = None
            entry_date = None

    final_close = float(work["close"].iloc[-1])
    final_equity = shares * final_close if in_position else cash
    latest = work.iloc[-1]
    v10 = safe_round(latest["vwap_10d"])
    v20 = safe_round(latest["vwap_20d"])
    v40 = safe_round(latest["vwap_40d"])
    latest_date = str(work.index[-1].date())
    buy_now = v10 is not None and v20 is not None and v40 is not None and v10 > v20 > v40
    sell_now = v10 is not None and v20 is not None and v10 < v20
    alignment = "N/A" if None in (v10, v20, v40) else ("10 > 20 > 40" if v10 > v20 > v40 else "10 < 20 < 40" if v10 < v20 < v40 else "mixed")
    action = "보유 유지" if in_position and not sell_now else "매도 신호" if in_position and sell_now else "매수 대기" if not in_position and not buy_now else "매수 신호"
    current_trade_return = pct_change(entry_price, final_close) if in_position and entry_price is not None else None
    holding_days = None
    if in_position and entry_date:
        holding_days = len(work.loc[pd.Timestamp(entry_date):])

    strategy_return = (final_equity - 1) * 100
    bh_return = pct_change(float(work["open"].iloc[0]), final_close)
    wins = [t for t in trades if t.get("return_pct") is not None and t["return_pct"] > 0]

    return {
        "available": True,
        "strategy": "VWAP 10/20/40",
        "rules": {"buy": "VWAP10 > VWAP20 > VWAP40", "sell": "VWAP10 < VWAP20", "fee_one_way_pct": 0.03},
        "latest": {
            "date": latest_date,
            "vwap10": v10, "vwap20": v20, "vwap40": v40,
            "alignment": alignment, "in_position": in_position, "action": action,
            "last_signal": last_signal, "last_signal_date": last_signal_date,
            "holding_days": holding_days,
            "entry_date": entry_date, "entry_price": safe_round(entry_price),
            "current_trade_return_pct": safe_round(current_trade_return, 2),
        },
        "backtest": {
            "start_date": str(work.index[0].date()), "end_date": latest_date,
            "strategy_return_pct": safe_round(strategy_return, 2),
            "buy_hold_return_pct": safe_round(bh_return, 2),
            "max_drawdown_pct": safe_round(calc_max_drawdown(equity_curve), 2),
            "trades": len(trades),
            "win_rate_pct": safe_round(len(wins) / len(trades) * 100 if trades else None, 2),
        },
        "signals": signals[-80:],
    }


# ──────────────────────────────────────────────────────────
# 종목별 데이터 처리
# ──────────────────────────────────────────────────────────
def download_ohlcv(ticker: str, end_date: str) -> pd.DataFrame:
    """yfinance에서 OHLCV 데이터 다운로드."""
    raw = yf.download(
        ticker,
        start=DATA_START,
        end=end_date,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    raw.columns = [c[0].lower() for c in raw.columns]
    return raw[["open", "high", "low", "close", "volume"]].dropna().copy()


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


def build_weekly_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """주간 시계열 레코드 생성."""
    df = df.copy()
    df["vwap"] = compute_proxy_vwap_series(df, window=20)
    df["vwap_prev5"] = pd.Series(df["vwap"].values, index=df.index).shift(5)
    df["weekly_chg"] = (df["vwap"] - df["vwap_prev5"]) / df["vwap_prev5"] * 100
    df["week"] = df.index.isocalendar().week.values
    df["year"] = df.index.year

    weekly_idx = [grp.index[-1] for (_, _), grp in df.groupby(["year", "week"])]
    weekly = df.loc[weekly_idx].copy()
    weekly["score"] = strength_score(weekly["weekly_chg"].tolist())
    weekly = weekly[
        [
            date.fromisoformat(str(d.date())) >= WEEKLY_CUTOFF
            and str(d.date()) not in EXCLUDE_DATES
            for d in weekly.index
        ]
    ]

    return [
        {
            "date": str(dt.date()),
            "price": round(float(row["close"]), 2),
            "score": None if pd.isna(row["score"]) else float(row["score"]),
        }
        for dt, row in weekly.iterrows()
    ]


def build_vwap_momentum_matrix(df: pd.DataFrame) -> dict[str, Any]:
    """VWAP 기간 구조의 100셀 모멘텀 행렬을 생성."""
    vwap_by_window: dict[int, float] = {}
    for window in WINDOWS:
        if len(df) >= window:
            vwap_by_window[window] = compute_vwap(df.iloc[-window:])

    momentum_decay = 0.75
    cells: list[dict[str, Any]] = []
    row_scores: list[float] = []
    weights = [10 * momentum_decay**i for i in range(10)]
    total_weight = sum(weights)
    weighted_sum = 0.0

    for i in range(10):
        endpoint = (i + 1) * 10
        cell_weighted_sum = 0.0
        cell_total_weight = 0.0
        for j in range(1, 11):
            start = endpoint + j * 10
            if endpoint not in vwap_by_window or start not in vwap_by_window:
                continue
            cell_momentum = (vwap_by_window[endpoint] / vwap_by_window[start]) ** (1 / j) - 1
            cell_weight = 10 * momentum_decay ** (j - 1)  # +10d 비교 가중 높음
            cells.append({
                "endpoint": endpoint,
                "start": start,
                "score": round(cell_momentum, 6),
            })
            cell_weighted_sum += cell_weight * cell_momentum
            cell_total_weight += cell_weight
        row_score = cell_weighted_sum / cell_total_weight if cell_total_weight > 0 else 0.0
        row_scores.append(round(row_score, 6))
        weighted_sum += weights[i] * row_score

    momentum = weighted_sum / total_weight if total_weight > 0 else 0.0
    return {
        "cells": cells,
        "row_scores": row_scores,
        "momentum": round(momentum, 6),
    }


def build_detail_data(name: str, ticker: str, df: pd.DataFrame) -> dict[str, Any]:
    """detail.html용 상세 데이터 생성."""
    # ohlcv: 최근 200일 + 전략용 VWAP 10/20/40 롤링
    tail = df.iloc[-200:].copy()
    vwap10_series = compute_proxy_vwap_series(tail, window=10)
    vwap20_series = compute_proxy_vwap_series(tail, window=20)
    vwap40_series = compute_proxy_vwap_series(tail, window=40)
    ohlcv = []
    for i, (dt, row) in enumerate(tail.iterrows()):
        rec: dict[str, Any] = {
            "date": str(dt.date()),
            "open": round(float(row["open"]), 4),
            "high": round(float(row["high"]), 4),
            "low": round(float(row["low"]), 4),
            "close": round(float(row["close"]), 4),
            "volume": int(row["volume"]),
        }
        rec["vwap_10d"] = safe_round(vwap10_series[i])
        rec["vwap_20d"] = safe_round(vwap20_series[i])
        rec["vwap_40d"] = safe_round(vwap40_series[i])
        ohlcv.append(rec)

    # volume_profile: 10d~200d (20개 전체)
    volume_profile: dict[str, Any] = {}
    for period in range(10, 201, 10):
        if len(df) >= period:
            vwap_val, buckets = compute_vwap_with_profile(df.iloc[-period:])
            volume_profile[f"{period}d"] = {
                "buckets": buckets,
                "vwap": round(vwap_val, 4),
            }

    return {
        "name": name,
        "ticker": ticker,
        "ohlcv": ohlcv,
        "volume_profile": volume_profile,
        "vwap_momentum_matrix": build_vwap_momentum_matrix(df),
        "strategy_signal": build_strategy_signal(df),
        "latest_price": round(float(df["close"].iloc[-1]), 2),
    }


def process_asset(
    name: str, ticker: str, group: str, end_date: str
) -> dict[str, Any] | None:
    """단일 종목 처리. 실패 시 None 반환."""
    print(f"  {name} ({ticker})...")
    try:
        df = download_ohlcv(ticker, end_date)
    except Exception as e:
        print(f"    [ERROR] {name}: {e}")
        return None

    if df.empty:
        print(f"    [WARN] {name}: 데이터 없음")
        return None

    vwap_structure, _ = build_vwap_structure(df)
    records = build_weekly_records(df)

    s = vwap_structure
    print(f"    200d={s[-1].get('norm')} / 10d={s[0].get('norm')}")

    return {
        "ticker": ticker,
        "group": group,
        "records": records,
        "vwap_structure": vwap_structure,
        "strategy_signal": build_strategy_signal(df),
        "latest_price": round(float(df["close"].iloc[-1]), 2),
    }


# ──────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────
def main() -> None:
    run_time = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    end_date = datetime.now(KST).strftime("%Y-%m-%d")

    result: dict[str, Any] = {"_meta": {"updated_at": run_time}}
    failed: list[str] = []

    for name, ticker, group in ASSETS:
        asset_data = process_asset(name, ticker, group, end_date)
        if asset_data is not None:
            result[name] = asset_data
        else:
            failed.append(name)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, allow_nan=False)

    # detail_data/ 생성
    os.makedirs(DETAIL_DIR, exist_ok=True)
    print("\n📊 detail_data 생성 중...")
    for name, ticker, _group in ASSETS:
        if name in failed or name not in result:
            continue
        try:
            df = download_ohlcv(ticker, end_date)
            if df.empty:
                continue
            detail = build_detail_data(name, ticker, df)
            detail["_meta"] = {"updated_at": run_time}
            out_path = os.path.join(DETAIL_DIR, f"{ticker}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(detail, f, ensure_ascii=False, allow_nan=False)
            print(f"  ✅ {name} → {out_path}")
        except Exception as e:
            print(f"  [ERROR] detail {name}: {e}")

    print(f"\n✅ 저장 완료: {OUTPUT_PATH}  (기준: {run_time})")
    if failed:
        print(f"⚠️  실패 종목: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
