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
    # 그룹 1
    ("TLT",                        "TLT",       "g1"),
    ("GLD",                        "GLD",       "g1"),
    ("IBIT",                       "IBIT",      "g1"),
    ("SPY",                        "SPY",       "g1"),
    ("QQQ",                        "QQQ",       "g1"),
    # 그룹 2
    ("SOL 미국테크TOP10",            "481190.KS", "g2"),
    ("TIGER 미국필라델피아반도체나스닥", "381180.KS", "g2"),
    ("KODEX 미국반도체",              "390390.KS", "g2"),
    ("ACE 글로벌반도체TOP4 Plus",     "446770.KS", "g2"),
    ("엔비디아",                      "NVDA",      "g2"),
    ("알파벳",                        "GOOGL",     "g2"),
    ("애플",                          "AAPL",      "g2"),
    ("마이크로소프트",                 "MSFT",      "g2"),
    ("아마존",                        "AMZN",      "g2"),
    ("메타",                          "META",      "g2"),
    ("브로드컴",                      "AVGO",      "g2"),
    ("테슬라",                        "TSLA",      "g2"),
    ("넷플릭스",                      "NFLX",      "g2"),
    ("팔란티어",                      "PLTR",      "g2"),
    ("시스코",                        "CSCO",      "g2"),
    # 그룹 3
    ("KODEX 200",                    "069500.KS", "g3"),
    ("KODEX 코스닥150",               "229200.KS", "g3"),
    ("KODEX 반도체",                  "091160.KS", "g3"),
    ("KODEX AI반도체",                "395160.KS", "g3"),
    ("KODEX AI반도체핵심장비",          "471990.KS", "g3"),
    ("TIGER 반도체TOP10",             "396500.KS", "g3"),
    ("삼성전자",                      "005930.KS", "g3"),
    ("SK하이닉스",                    "000660.KS", "g3"),
    ("한미반도체",                    "042700.KS", "g3"),
    ("리노공업",                      "058470.KS", "g3"),
]

WINDOWS: list[int] = list(range(10, 201, 10))  # 10~200, 10일 간격
N_BUCKETS: int = 20
KST: timezone = timezone(timedelta(hours=9))
DATA_START: str = "2023-01-01"
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
    df["vwap"] = compute_vwap_series(df, window=20)
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
            "score": row["score"],
        }
        for dt, row in weekly.iterrows()
    ]


def build_detail_data(name: str, ticker: str, df: pd.DataFrame) -> dict[str, Any]:
    """detail.html용 상세 데이터 생성."""
    # ohlcv: 최근 200일 + vwap_10d 롤링
    tail = df.iloc[-200:].copy()
    vwap_series = compute_vwap_series(tail, window=10)
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
        rec["vwap_10d"] = round(vwap_series[i], 4) if vwap_series[i] is not None else None
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

    # sci_matrix: vwap_map에서 100셀 계산
    vmap: dict[int, float] = {}
    for w in WINDOWS:
        if len(df) >= w:
            vmap[w] = compute_vwap(df.iloc[-w:])

    sci_threshold = 0.01
    sci_decay = 0.75
    cells: list[dict[str, Any]] = []
    row_scores: list[float] = []
    weights = [10 * sci_decay**i for i in range(10)]
    total_weight = sum(weights)
    weighted_sum = 0.0

    for i in range(10):
        endpoint = (i + 1) * 10
        above_count = 0
        total_count = 0
        for j in range(1, 11):
            start = endpoint + j * 10
            if endpoint not in vmap or start not in vmap:
                continue
            slope = (vmap[endpoint] - vmap[start]) / j
            is_above = slope > vmap[start] * sci_threshold
            cells.append({
                "endpoint": endpoint,
                "start": start,
                "slope": round(slope, 6),
                "above": is_above,
            })
            if is_above:
                above_count += 1
            total_count += 1
        rs = above_count / total_count if total_count > 0 else 0.0
        row_scores.append(round(rs, 4))
        weighted_sum += weights[i] * rs

    sci_val = weighted_sum / total_weight if total_weight > 0 else 0.0

    sci_matrix = {
        "cells": cells,
        "row_scores": row_scores,
        "sci": round(sci_val, 4),
        "threshold": sci_threshold,
    }

    return {
        "name": name,
        "ticker": ticker,
        "ohlcv": ohlcv,
        "volume_profile": volume_profile,
        "sci_matrix": sci_matrix,
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
        json.dump(result, f, ensure_ascii=False)

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
                json.dump(detail, f, ensure_ascii=False)
            print(f"  ✅ {name} → {out_path}")
        except Exception as e:
            print(f"  [ERROR] detail {name}: {e}")

    print(f"\n✅ 저장 완료: {OUTPUT_PATH}  (기준: {run_time})")
    if failed:
        print(f"⚠️  실패 종목: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
