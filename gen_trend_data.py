"""VWAP 추세 데이터 생성기.

yfinance에서 주가 데이터를 받아 VWAP와 정규분포 기반 Volume Profile을 계산하고,
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
    ("KODEX 미국AI전력핵심인프라",      "487230.KS"),
    ("SOL 미국AI전력인프라",            "486450.KS"),
    ("TIGER 글로벌AI전력인프라액티브",    "491010.KS"),

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
    ("PLUS 태양광&ESS",              "457990.KS"),
    ("한화솔루션",                    "009830.KS"),
    ("OCI홀딩스",                    "010060.KS"),
    ("HD현대에너지솔루션",              "322000.KS"),
    ("대명에너지",                     "389260.KQ"),
    ("신성이엔지",                     "011930.KS"),
    ("SDN",                          "099220.KQ"),
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
    ("ACE K휴머노이드로봇산업TOP2+",    "0177X0.KS"),
    ("TIGER 코리아휴머노이드로봇산업",    "0148J0.KS"),
    ("레인보우로보틱스",                 "277810.KQ"),
    ("로보티즈",                         "108490.KQ"),
    ("에스피지",                         "058610.KQ"),
    ("두산로보틱스",                      "454910.KS"),
    ("TIGER 화장품",                   "228790.KS"),
    ("KODEX 필수소비재",               "266410.KS"),
    ("삼양식품",                        "003230.KS"),
    ("SK텔레콤",                        "017670.KS"),
]

WINDOWS: list[int] = [5, 20, 60, 120, 240]  # 1d는 명시적 proxy, 나머지는 상세 차트용 롤링 VWAP 기간
VOLUME_PROFILE_WINDOWS: list[int] = [1, 5, 20, 60, 120, 240]  # 하단 Volume Profile 기간
STORAGE_TRADING_DAYS: int = 480  # 240일 차트와 VWAP240 준비구간을 함께 저장
HISTORY_TRADING_DAYS: int = STORAGE_TRADING_DAYS
MIN_SIGNAL_TRADING_DAYS: int = 25  # 신규 종목도 표에 유지하고, 미산출 기간이 필요한 신호만 WAIT
DOWNLOAD_CALENDAR_DAYS: int = 1300  # 휴장일을 고려해 저장용 480거래일을 안정적으로 확보
N_BUCKETS: int = 20
KST: timezone = timezone(timedelta(hours=9))
KRX_TODAY_PATCH_AFTER = time(15, 30)  # 장중 Naver 일봉은 미확정값이므로 15:30 이후만 반영
EXCLUDE_DATES: frozenset[str] = frozenset({"2025-12-31", "2025-12-30", "2025-12-29"})
OUTPUT_PATH: str = "trend_data.json"
DETAIL_DIR: str = "detail_data"


def compute_vwap_with_profile(
    df_window: pd.DataFrame,
) -> tuple[float | None, list[dict[str, float]]]:
    """정확한 대표가격 VWAP와 정규분포 기반 프로필 버킷 배열을 반환."""
    exact_vwap = compute_proxy_vwap_series(df_window, len(df_window))[-1]
    lo = float(df_window["low"].min())
    hi = float(df_window["high"].max())
    if hi == lo:
        mid = float(df_window["close"].mean())
        return exact_vwap, [{"price": mid, "volume": 0.0} for _ in range(N_BUCKETS)]

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

    buckets = [
        {"price": round(float(bucket_prices[i]), 4), "volume": round(float(bvol[i]), 2)}
        for i in range(N_BUCKETS)
    ]
    return exact_vwap, buckets


def typical_price_series(df: pd.DataFrame) -> pd.Series:
    """일봉 OHLC의 대표가격 `(high + low + close) / 3`."""
    return (
        cast(pd.Series, df["high"])
        + cast(pd.Series, df["low"])
        + cast(pd.Series, df["close"])
    ) / 3


def compute_proxy_vwap_series(df: pd.DataFrame, window: int) -> list[float | None]:
    """상세 차트와 현재 정배열 신호용 빠른 일봉 VWAP proxy.

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


def date_key(value: Any) -> str:
    """DatetimeIndex/Hashable 값을 JSON용 YYYY-MM-DD 문자열로 변환."""
    return str(pd.Timestamp(value).date())


ALIGNMENT_5_20 = "alignment_5_20"
ALIGNMENT_20_60 = "alignment_20_60"
ALIGNMENT_60_120 = "alignment_60_120"
ALIGNMENT_STRATEGIES: dict[str, dict[str, Any]] = {
    ALIGNMENT_5_20: {
        "label": "5 > 20",
        "rule": "VWAP5 > VWAP20",
        "windows": (5, 20),
    },
    ALIGNMENT_20_60: {
        "label": "20 > 60",
        "rule": "VWAP20 > VWAP60",
        "windows": (20, 60),
    },
    ALIGNMENT_60_120: {
        "label": "60 > 120",
        "rule": "VWAP60 > VWAP120",
        "windows": (60, 120),
    },
}


def prepare_storage_frame(df: pd.DataFrame) -> pd.DataFrame:
    """최근 480거래일에 VWAP 지표를 계산해 저장·현재 신호에 함께 사용한다.

    앞 239개 저장 행의 VWAP240은 준비구간이라 None일 수 있다. 가격 차트는
    마지막 240개 행만 사용하므로 표시 첫날부터 VWAP240이 유효하다.
    """
    source = df.tail(STORAGE_TRADING_DAYS).copy()
    source["vwap_1d"] = typical_price_series(source).astype(float)
    for window in WINDOWS:
        source[f"vwap_{window}d"] = compute_proxy_vwap_series(source, window)
    return source


def strict_alignment_signal(*values: Any) -> str:
    """주어진 VWAP 값의 엄격한 내림차순 배열을 BUY/SELL/WAIT로 변환."""
    if any(is_missing(value) for value in values):
        return "WAIT"
    numeric = [float(value) for value in values]
    return "BUY" if all(
        left > right for left, right in zip(numeric, numeric[1:])
    ) else "SELL"


def alignment_signal(row: pd.Series, strategy_key: str) -> str:
    """정배열 키에 해당하는 최신 실시간 상태를 반환한다."""
    definition = ALIGNMENT_STRATEGIES.get(strategy_key)
    if definition is None:
        raise ValueError(f"unknown alignment strategy: {strategy_key}")
    return strict_alignment_signal(*(
        row.get(f"vwap_{window}d") for window in definition["windows"]
    ))


def build_latest_alignment_snapshot(
    work: pd.DataFrame,
    strategy_key: str,
) -> dict[str, Any]:
    """한 정배열 정의에 필요한 최신 값과 현재 신호만 직렬화한다."""
    if work.empty:
        return {
            "date": None,
            "vwap1": None,
            "vwap5": None,
            "vwap20": None,
            "vwap60": None,
            "vwap120": None,
            "signal": "WAIT",
            "alignment": "N/A",
        }

    latest = work.iloc[-1]
    signal = alignment_signal(latest, strategy_key)
    label = ALIGNMENT_STRATEGIES[strategy_key]["label"]
    alignment = {
        "WAIT": "N/A",
        "BUY": label,
        "SELL": "정배열 아님",
    }[signal]
    return {
        "date": date_key(work.index[-1]),
        "vwap1": safe_round(latest.get("vwap_1d")),
        "vwap5": safe_round(latest.get("vwap_5d")),
        "vwap20": safe_round(latest.get("vwap_20d")),
        "vwap60": safe_round(latest.get("vwap_60d")),
        "vwap120": safe_round(latest.get("vwap_120d")),
        "signal": signal,
        "alignment": alignment,
    }


def build_strategy_signal(df: pd.DataFrame) -> dict[str, Any]:
    """세 가지 엄격한 VWAP 구간 비교의 최신 상태만 생성한다."""
    work = prepare_storage_frame(df)
    strategies = {
        strategy_key: {
            "label": definition["label"],
            "rule": definition["rule"],
            "windows": list(definition["windows"]),
            "latest": build_latest_alignment_snapshot(work, strategy_key),
        }
        for strategy_key, definition in ALIGNMENT_STRATEGIES.items()
    }
    available = len(df) >= MIN_SIGNAL_TRADING_DAYS
    result: dict[str, Any] = {
        "available": available,
        "strategies": strategies,
    }
    if not available:
        result["reason"] = "insufficient_recent_history"
    return result


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
    """저장용 최근 480거래일 OHLCV를 다운로드한다."""
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


def build_detail_data(
    name: str,
    ticker: str,
    df: pd.DataFrame,
    strategy_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """가격 차트, Volume Profile, 현재 정배열 신호의 상세 데이터를 생성한다."""
    if strategy_signal is None:
        strategy_signal = build_strategy_signal(df)

    work = prepare_storage_frame(df)
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
                "vwap": safe_round(vwap_val),
            }

    return {
        "name": name,
        "ticker": ticker,
        "ohlcv": ohlcv,
        "volume_profile": volume_profile,
        "strategy_signal": strategy_signal,
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
    strategy_signal = build_strategy_signal(df)

    asset_result = {
        "ticker": ticker,
        "strategy_signal": strategy_signal,
    }
    attach_krx_data_source(asset_result, df)
    detail_result = build_detail_data(
        name,
        ticker,
        df,
        strategy_signal=strategy_signal,
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
    print("    완료")
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
            "storage_trading_days": STORAGE_TRADING_DAYS,
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
