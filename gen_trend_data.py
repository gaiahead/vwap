"""ETF discovery metadata and full daily history; run --help for offline migration."""
from __future__ import annotations
import argparse
import ast
import json
import os
import re
from pathlib import Path
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, cast
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.stats import norm

ASSETS: list[tuple[str, str]] = [
    ('TIGER 토탈월드스탁액티브', '0060H0.KS'),
    ('KODEX 미국S&P500', '379800.KS'),
    ('KODEX 미국나스닥100', '379810.KS'),
    ('TIGER 미국배당다우존스', '458730.KS'),
    ('KODEX 미국S&P500금융', '453650.KS'),
    ('KODEX 미국S&P500헬스케어', '453640.KS'),
    ('TIGER 미국나스닥바이오', '203780.KS'),
    ('SOL 미국테크TOP10', '481190.KS'),
    ('TIME 글로벌AI인공지능액티브', '456600.KS'),
    ('TIGER 미국필라델피아반도체나스닥', '381180.KS'),
    ('KODEX 미국반도체', '390390.KS'),
    ('ACE 글로벌반도체TOP4 Plus', '446770.KS'),
    ('KODEX 미국AI전력핵심인프라', '487230.KS'),
    ('SOL 미국AI전력인프라', '486450.KS'),
    ('TIGER 글로벌AI전력인프라액티브', '491010.KS'),
    ('KODEX 200', '069500.KS'),
    ('KODEX 200 레버리지', '122630.KS'),
    ('KODEX 코스닥150', '229200.KS'),
    ('KODEX 코스닥150 레버리지', '233740.KS'),
    ('KODEX 반도체', '091160.KS'),
    ('KODEX AI반도체TOP2플러스', '395160.KS'),
    ('KODEX AI반도체핵심장비', '471990.KS'),
    ('ACE AI반도체TOP3+', '469150.KS'),
    ('SOL 반도체전공정', '475300.KS'),
    ('SOL 반도체후공정', '475310.KS'),
    ('SOL AI반도체소부장', '455850.KS'),
    ('KODEX AI전력핵심설비', '487240.KS'),
    ('TIGER 코리아AI전력기기TOP3플러스', '0117V0.KS'),
    ('TIGER 반도체TOP10', '396500.KS'),
    ('HANARO 원자력iSelect', '434730.KS'),
    ('KIWOOM 미국원유에너지기업', '474800.KS'),
    ('KoAct 미국천연가스인프라액티브', '497780.KS'),
    ('RISE 미국천연가스밸류체인', '0036Z0.KS'),
    ('PLUS 글로벌희토류&전략자원생산기업', '415920.KS'),
    ('PLUS 태양광&ESS', '457990.KS'),
    ('KODEX 자동차', '091180.KS'),
    ('KODEX 은행', '091170.KS'),
    ('KODEX 2차전지산업', '305720.KS'),
    ('KODEX 철강', '117680.KS'),
    ('KODEX 헬스케어', '266420.KS'),
    ('KODEX 조선TOP10', '0115D0.KS'),
    ('KODEX 방산TOP10', '0080G0.KS'),
    ('KODEX 건설', '117700.KS'),
    ('KODEX 운송', '140710.KS'),
    ('KODEX 금융고배당TOP10', '498410.KS'),
    ('KODEX 증권', '102970.KS'),
    ('KODEX 보험', '140700.KS'),
    ('TIGER 소프트웨어', '157490.KS'),
    ('KODEX IT', '266370.KS'),
    ('TIGER 미디어컨텐츠', '228810.KS'),
    ('KODEX 로봇액티브', '445290.KS'),
    ('ACE K휴머노이드로봇산업TOP2+', '0177X0.KS'),
    ('TIGER 코리아휴머노이드로봇산업', '0148J0.KS'),
    ('TIGER 화장품', '228790.KS'),
    ('KODEX 필수소비재', '266410.KS'),
]

WINDOWS: list[int] = [1, 20, 60, 240]
VOLUME_PROFILE_WINDOWS = WINDOWS
N_BUCKETS = 20
KST = timezone(timedelta(hours=9))
KRX_TODAY_PATCH_AFTER = time(15, 30)
DETAIL_DIR = "detail_data"
NAVER_ETF_URL = "https://finance.naver.com/api/sise/etfItemList.nhn"
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
ISSUER_PREFIXES = {
    "KODEX": "삼성자산운용", "KoAct": "삼성액티브자산운용",
    "TIGER": "미래에셋자산운용", "SOL": "신한자산운용",
    "ACE": "한국투자신탁운용", "TIME": "타임폴리오자산운용",
    "HANARO": "NH-Amundi자산운용", "KIWOOM": "키움투자자산운용",
    "RISE": "KB자산운용", "PLUS": "한화자산운용",
}
CATEGORY_KEYWORDS = [
    (("레버리지",), "레버리지"),
    (("반도체",), "반도체"),
    (("AI전력", "전력기기", "전력핵심"), "AI 및 전력 인프라"),
    (("원유", "천연가스", "희토류", "태양광", "원자력"), "에너지 및 자원"),
    (("금융", "은행", "증권", "보험"), "금융"),
    (("헬스케어", "바이오"), "헬스케어 및 바이오"),
    (("2차전지",), "2차전지"),
    (("자동차",), "자동차"),
    (("조선",), "조선"),
    (("방산",), "방산"),
    (("건설",), "건설"),
    (("운송",), "운송"),
    (("로봇", "휴머노이드"), "로봇"),
    (("소프트웨어", "미디어컨텐츠", " IT"), "IT 및 콘텐츠"),
    (("화장품", "필수소비재"), "소비재"),
    (("S&P500", "나스닥100", "토탈월드", "KODEX 200", "코스닥150", "배당다우존스"), "대표지수 및 배당"),
]


def derive_registry_facts(name: str | None) -> dict[str, str]:
    """상품명으로 검색용 운용사와 분석 분류를 일관되게 부여한다."""
    if not name:
        return {}
    issuer = next((value for prefix, value in ISSUER_PREFIXES.items() if name.startswith(prefix)), None)
    theme = next((label for keywords, label in CATEGORY_KEYWORDS if any(key in name for key in keywords)), "기타 주식")
    region = "해외" if any(key in name for key in ("미국", "글로벌", "토탈월드")) else "국내"
    result = {"category": f"{region} 주식, {theme}", "exposure": name}
    if issuer:
        result["issuer"] = issuer
    return result


def safe_round(value, digits=4):
    try:
        number = float(value)
        return round(number, digits) if np.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def history_start(end_date):
    return (pd.Timestamp(end_date) - pd.DateOffset(years=20)).date().isoformat()


def clean_frame(df, end_date):
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.loc[history_start(end_date):end_date, OHLCV_COLUMNS]
    df = df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return df[(df[OHLCV_COLUMNS[:4]] > 0).all(axis=1) & (df.volume >= 0)]


def prepare_storage_frame(df):
    source = df.copy()
    for window in WINDOWS:
        source[f"vwap_{window}d"] = compute_proxy_vwap_series(source, window)
    return source


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
    """상세 차트용 빠른 일봉 VWAP proxy.

    대표가격 = (High + Low + Close) / 3, n일 VWAP = Σ(대표가격×거래량)/Σ거래량.
    거래량 합계가 0인 구간은 JSON에 NaN/Infinity가 새지 않도록 None으로 둔다.
    """
    volume = cast(pd.Series, df["volume"])
    typical = typical_price_series(df)
    pv = typical * volume
    denom = cast(pd.Series, volume.rolling(window).sum()).replace(0, np.nan)
    series = pv.rolling(window).sum() / denom
    return [None if pd.isna(v) else float(v) for v in series.tolist()]

def date_key(value: Any) -> str:
    """DatetimeIndex/Hashable 값을 JSON용 YYYY-MM-DD 문자열로 변환."""
    return str(pd.Timestamp(value).date())

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

    Yahoo/yfinance는 장 마감 직후 같은 날짜 행을 주더라도 KRX ETF/ETF의
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
    patched = patched.sort_index().copy()
    patched.attrs["krx_today_patched"] = True
    patched.attrs["krx_today_source"] = "naver_siseJson"
    patched.attrs["krx_today_date"] = today.isoformat()
    return patched

def remove_unregistered_detail_files() -> list[str]:
    """등록 목록에서 제거된 ETF의 오래된 상세 JSON을 삭제한다."""
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


def download_ohlcv(ticker: str, end_date: str) -> pd.DataFrame:
    yf.set_tz_cache_location(str(Path(__file__).parent / ".local-run" / "yfinance"))
    raw = yf.download(ticker, start=history_start(end_date),
                      end=(pd.Timestamp(end_date) + pd.Timedelta(days=1)).date().isoformat(),
                      interval="1d", auto_adjust=True, progress=False, timeout=20)
    raw.columns = [(c[0] if isinstance(c, tuple) else c).lower() for c in raw.columns]
    if raw.empty:
        raise ValueError(f"No history returned for {ticker}")
    df = clean_frame(raw, end_date)
    return clean_frame(maybe_patch_krx_today(df, ticker, date.fromisoformat(end_date)), end_date)


def fetch_naver_etf_list():
    try:
        response = requests.get(NAVER_ETF_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        payload = None
        for encoding in ("utf-8-sig", "cp949"):
            try:
                payload = json.loads(response.content.decode(encoding))
                break
            except (UnicodeDecodeError, ValueError):
                continue
        if payload is None:
            raise ValueError("Unsupported ETF response encoding")
        items = payload["result"]["etfItemList"]
        return {str(row["itemcode"]): row for row in items if isinstance(row, dict) and row.get("itemcode")}
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        print(f"[WARN] ETF market metadata unavailable: {error}")
        return {}


def load_optional_facts(path="etf_facts.json"):
    """Audited optional values only; every populated field requires its own citation."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {t for _, t in ASSETS}
    result = {}
    numeric = {"total_expense_ratio_pct", "actual_total_cost_pct", "other_cost_pct", "synthetic_total_expense_ratio_pct", "trading_cost_pct"}
    allowed = numeric | {"category", "issuer", "benchmark", "exposure", "holdings"}
    for ticker, fields in payload.get("etfs", {}).items():
        if ticker not in known:
            raise ValueError(f"Unregistered ETF facts: {ticker}")
        result[ticker] = {}
        for field, record in fields.items():
            if field not in allowed or not isinstance(record, dict):
                raise ValueError(f"Invalid facts field: {field}")
            if not str(record.get("source_url", "")).startswith("https://"):
                raise ValueError(f"Source required: {ticker}/{field}")
            date.fromisoformat(record["as_of"])
            value = record["value"]
            if field in numeric and (safe_round(value) is None or float(value) < 0):
                raise ValueError(f"Invalid cost: {ticker}/{field}")
            if field == "holdings":
                if not isinstance(value, list) or any(
                    not isinstance(h, dict) or not h.get("name") or
                    (h.get("weight_pct") is not None and
                     (safe_round(h["weight_pct"]) is None or not 0 <= h["weight_pct"] <= 100))
                    for h in value
                ):
                    raise ValueError(f"Invalid holdings: {ticker}")
                weights = [h["weight_pct"] for h in value if h.get("weight_pct") is not None]
                if sum(weights) > 100.1:
                    raise ValueError(f"Invalid holdings weights: {ticker}")
            elif field not in numeric and not isinstance(value, str):
                raise ValueError(f"Invalid text: {ticker}/{field}")
            result[ticker][field] = record
    return result


def build_facts(ticker, df, market=None, as_of=None, optional=None, name=None):
    market = market or {}
    facts = dict.fromkeys(["category", "issuer", "benchmark", "exposure", "aum_krw",
                          "avg_volume_20d", "avg_trading_value_20d_krw",
                          "total_expense_ratio_pct", "actual_total_cost_pct", "other_cost_pct",
                          "premium_discount_pct", "top10_weight_pct", "holdings_summary",
                          "synthetic_total_expense_ratio_pct", "trading_cost_pct"])
    facts.update(holdings=[], sources={})
    facts.update(derive_registry_facts(name))
    for field, record in (optional or {}).items():
        facts[field] = record["value"]
        facts["sources"][field] = {"url": record["source_url"], "as_of": record["as_of"], "note": record.get("note")}
    aum, price, nav = (safe_round(market.get(k)) for k in ["marketSum", "nowVal", "nav"])
    facts["aum_krw"] = aum * 100_000_000 if aum is not None and aum >= 0 else None
    facts["premium_discount_pct"] = safe_round((price / nav - 1) * 100) if price is not None and nav is not None and nav > 0 else None
    if market:
        facts["sources"]["market"] = {"url": NAVER_ETF_URL, "as_of": market.get("as_of"),
            "retrieved_at": as_of, "note": "Endpoint has no guaranteed quote timestamp; retrieval time is not quote time.",
            "marketSum_unit": "억원",
            "raw": {key: safe_round(market.get(key)) for key in ("marketSum", "quant", "amonut", "nowVal", "nav")}}
    if len(df) >= 20:
        recent = df.tail(20)
        facts["avg_volume_20d"] = safe_round(recent.volume.mean())
        facts["avg_trading_value_20d_krw"] = safe_round((recent.close * recent.volume).mean())
        facts["sources"]["liquidity"] = {"url": f"https://finance.yahoo.com/quote/{ticker}/history/",
            "as_of": date_key(df.index[-1]), "from": date_key(recent.index[0]),
            "method": "20 trading rows; mean(volume), mean(adjusted close × volume), trading value is an OHLCV estimate"}
    holdings = facts["holdings"]
    if holdings:
        facts["holdings_summary"] = ", ".join(h["name"] for h in holdings[:3])
        weighted = [h for h in holdings if h.get("weight_pct") is not None]
        if len(weighted) == len(holdings) and len(weighted) >= 10:
            facts["top10_weight_pct"] = safe_round(sum(sorted([h["weight_pct"] for h in weighted], reverse=True)[:10]))
    return facts


def build_asset_outputs(name, ticker, df, market=None, as_of=None, optional=None):
    facts = build_facts(ticker, df, market, as_of, optional, name=name)
    work = prepare_storage_frame(df)
    rows = []
    for dt, row in work.iterrows():
        rows.append({"date": date_key(dt), **{key: safe_round(row[key]) for key in OHLCV_COLUMNS},
                     **{f"vwap_{w}d": safe_round(row[f"vwap_{w}d"]) for w in WINDOWS}})
    profiles = {}
    for period in WINDOWS:
        if len(work) >= period:
            vwap, buckets = compute_vwap_with_profile(work.tail(period))
            profiles[f"{period}d"] = {"vwap": safe_round(vwap), "buckets": buckets}
    meta = {"url": f"https://finance.yahoo.com/quote/{ticker}/history/",
            "as_of": date_key(df.index[-1]) if len(df) else None,
            "first_date": date_key(df.index[0]) if len(df) else None,
            "rows": len(df), **df.attrs}
    brief = {"name": name, "ticker": ticker, **{k: v for k, v in facts.items() if k != "holdings"},
             "holdings_text": " ".join(str(h.get("name", "")) + " " + str(h.get("ticker", "")) for h in facts["holdings"]),
             "history_source": meta}
    detail = {"name": name, "ticker": ticker, "facts": facts, "ohlcv": rows,
              "volume_profile": profiles, "_meta": meta}
    return brief, detail


def write_json_file(path, payload):
    # Serialize before opening so invalid floats cannot truncate an existing artifact.
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    Path(path).write_text(encoded + "\n", encoding="utf-8")


def cached_history(ticker, end_date):
    path = Path(DETAIL_DIR) / f"{ticker}.json"
    if not path.exists():
        df = pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([]))
        df.attrs.update(status="unavailable", complete_history=False)
        return df
    cached = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(cached["ohlcv"], columns=["date", *OHLCV_COLUMNS]).set_index("date")
    df = clean_frame(df, end_date)
    df.attrs.update({k: v for k, v in cached.get("_meta", {}).items() if k.startswith("krx_today_")})
    df.attrs.update(status="cached", complete_history=False,
                    note="Live download unavailable; cached rows may omit earlier history.")
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default=datetime.now(KST).date().isoformat())
    parser.add_argument("--offline", action="store_true", help="Regenerate cached OHLCV only, explicitly marked incomplete; no network")
    parser.add_argument("--allow-cache", action="store_true", help="On download failure regenerate cached rows, explicitly marked incomplete")
    args = parser.parse_args()
    date.fromisoformat(args.end)
    now = datetime.now(KST).isoformat(timespec="seconds")
    market = {} if args.offline else fetch_naver_etf_list()
    optional = load_optional_facts()
    result = {"_meta": {"schema_version": 2, "updated_at": now, "end_date": args.end,
                       "history_start": history_start(args.end), "history_cap_years": 20,
                       "market_status": "available" if market else "unavailable"}, "etfs": []}
    details = {}
    failed = []
    for name, ticker in ASSETS:
        try:
            if args.offline:
                raise ValueError("offline regeneration")
            df = download_ohlcv(ticker, args.end)
            df.attrs.update(status="downloaded", complete_history=True, retrieved_at=now)
        except Exception as error:
            print(f"[WARN] {ticker}: {error}")
            failed.append(ticker)
            if not (args.offline or args.allow_cache):
                continue
            df = cached_history(ticker, args.end)
        brief, detail = build_asset_outputs(name, ticker, df, market.get(ticker.split('.')[0]), now, optional.get(ticker))
        result["etfs"].append(brief)
        details[ticker] = detail
    if failed and not (args.offline or args.allow_cache):
        raise SystemExit("Downloads failed; existing artifacts untouched. Use --allow-cache explicitly for partial history.")
    result["_meta"]["incomplete_history_count"] = len(failed)
    remove_unregistered_detail_files()
    for ticker, detail in details.items():
        write_json_file(Path(DETAIL_DIR) / f"{ticker}.json", detail)
    write_json_file("trend_data.json", result)
    print(f"Generated {len(details)} ETFs; incomplete histories: {len(failed)}")


if __name__ == "__main__":
    main()
