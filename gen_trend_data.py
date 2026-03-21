import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timezone, timedelta
from scipy.stats import norm
from datetime import date

ASSETS = [
    # 그룹 1
    ("TLT",             "TLT",       "g1"),
    ("GLD",             "GLD",       "g1"),
    ("IBIT",            "IBIT",      "g1"),
    # 그룹 2
    ("SPY",             "SPY",       "g2"),
    ("QQQ",             "QQQ",       "g2"),
    # 그룹 3
    ("SOL 미국테크TOP10", "481190.KS", "g3"),
    ("엔비디아",          "NVDA",      "g3"),
    ("알파벳",            "GOOGL",     "g3"),
    ("애플",              "AAPL",      "g3"),
    ("마이크로소프트",     "MSFT",      "g3"),
    ("아마존",            "AMZN",      "g3"),
    ("메타",              "META",      "g3"),
    ("브로드컴",          "AVGO",      "g3"),
    ("테슬라",            "TSLA",      "g3"),
    ("넷플릭스",          "NFLX",      "g3"),
    ("팔란티어",          "PLTR",      "g3"),
    # 그룹 4
    ("KODEX 200",        "069500.KS", "g4"),
    ("삼성전자",          "005930.KS", "g4"),
    ("SK하이닉스",        "000660.KS", "g4"),
    ("리노공업",          "058470.KS", "g4"),
]

WINDOWS = list(range(10, 201, 10))  # 10~200, 10일 간격
N_BUCKETS = 20

def compute_vwap(df_window):
    """정규분포 기반 Volume Profile VWAP"""
    lo = float(df_window["low"].min())
    hi = float(df_window["high"].max())
    if hi == lo:
        return float(df_window["close"].mean())

    bsize = (hi - lo) / N_BUCKETS
    bucket_prices = np.array([lo + (b + 0.5) * bsize for b in range(N_BUCKETS)])
    bvol = np.zeros(N_BUCKETS)

    for _, r in df_window.iterrows():
        # Typical Price = (고+저+종) / 3
        mu = (float(r["high"]) + float(r["low"]) + float(r["close"])) / 3
        sigma = (float(r["high"]) - float(r["low"])) / 4
        if sigma == 0:
            # 고저가 같으면 해당 버킷에 전량
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

def compute_vwap_series(df, window=20):
    vwaps = []
    for i in range(len(df)):
        if i < window:
            vwaps.append(None)
            continue
        vwaps.append(compute_vwap(df.iloc[i-window:i]))
    return vwaps

def strength_score(arr, norm_window=52):
    scores = []
    for i in range(len(arr)):
        v = arr[i]
        if v is None or (isinstance(v, float) and np.isnan(v)):
            scores.append(None); continue
        window_vals = [x for x in arr[max(0,i-norm_window):i+1]
                       if x is not None and not (isinstance(x,float) and np.isnan(x))]
        if len(window_vals) < 5:
            scores.append(None); continue
        pct = sum(1 for x in window_vals if x <= v) / len(window_vals)
        scores.append(round((pct * 2 - 1) * 100, 1))
    return scores

# 실행 시각 (KST)
KST = timezone(timedelta(hours=9))
run_time = datetime.now(KST).strftime("%Y-%m-%d 07:00")

result = {"_meta": {"updated_at": run_time}}
cutoff = date(2025, 1, 6)
exclude = {'2025-12-31', '2025-12-30', '2025-12-29'}

for name, ticker, group in ASSETS:
    print(f"  {name} ({ticker})...")
    raw = yf.download(ticker, start="2023-01-01",
                      end=datetime.now(KST).strftime("%Y-%m-%d"),
                      interval="1d", auto_adjust=True, progress=False)
    raw.columns = [c[0].lower() for c in raw.columns]
    df = raw[["open","high","low","close","volume"]].dropna().copy()

    # VWAP 기간 구조 (현재 기준 스냅샷)
    vwap_structure = []
    base_vwap = None
    for w in WINDOWS:
        if len(df) >= w:
            v = compute_vwap(df.iloc[-w:])
            if w == 200:
                base_vwap = v
            vwap_structure.append({"window": w, "vwap": round(v, 4)})
        else:
            vwap_structure.append({"window": w, "vwap": None})

    if base_vwap:
        for item in vwap_structure:
            if item["vwap"] is not None:
                item["norm"] = round(item["vwap"] / base_vwap * 100, 2)
            else:
                item["norm"] = None

    # 주간 시계열 (참고용)
    df["vwap"] = compute_vwap_series(df, window=20)
    df["vwap_prev5"] = pd.Series(df["vwap"].values, index=df.index).shift(5)
    df["weekly_chg"] = (df["vwap"] - df["vwap_prev5"]) / df["vwap_prev5"] * 100
    df["week"] = df.index.isocalendar().week.values
    df["year"] = df.index.year
    weekly_idx = [grp.index[-1] for (y,w), grp in df.groupby(["year","week"])]
    weekly = df.loc[weekly_idx].copy()
    weekly["score"] = strength_score(weekly["weekly_chg"].tolist())
    weekly = weekly[[
        date.fromisoformat(str(d.date())) >= cutoff and str(d.date()) not in exclude
        for d in weekly.index
    ]]

    records = []
    for dt, row in weekly.iterrows():
        records.append({
            "date":  str(dt.date()),
            "price": round(float(row["close"]), 2),
            "score": row["score"],
        })

    result[name] = {
        "ticker": ticker,
        "group":  group,
        "records": records,
        "vwap_structure": vwap_structure,
        "latest_price": round(float(df["close"].iloc[-1]), 2),
    }

    s = vwap_structure
    print(f"    200d={s[-1]['norm']} / 10d={s[0]['norm']}")

output_path = "/tmp/trend_data.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False)
print(f"\n✅ 저장 완료: {output_path}  (기준: {run_time})")
