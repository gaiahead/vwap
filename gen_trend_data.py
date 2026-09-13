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


def build_asset_outputs(name, ticker, df, market=None, as_of=None, optional=None, collector=None):
    facts = build_facts(ticker, df, market, as_of, optional, name=name)
    if collector is not None:
        collector.enrich(ticker, facts)
    work = prepare_storage_frame(df)
    rows = []
    for dt, row in work.iterrows():
        rows.append({"date": date_key(dt), **{key: safe_round(row[key]) for key in OHLCV_COLUMNS},
                     **{f"vwap_{w}d": safe_round(row[f"vwap_{w}d"]) for w in WINDOWS}})
    meta = {"url": f"https://finance.yahoo.com/quote/{ticker}/history/",
            "as_of": date_key(df.index[-1]) if len(df) else None,
            "first_date": date_key(df.index[0]) if len(df) else None,
            "rows": len(df), **df.attrs}
    brief = {"name": name, "ticker": ticker, **{k: v for k, v in facts.items() if k != "holdings"},
             "holdings_text": " ".join(str(h.get("name", "")) + " " + str(h.get("ticker", "")) for h in facts["holdings"]),
             "history_source": meta}
    detail = {"name": name, "ticker": ticker, "facts": facts, "ohlcv": rows, "_meta": meta}
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


# Public K-ETF browser bundle eee787d0b8d7120b.js, not a private credential.
KETF_TOKEN = 'd3558a5223371268350260f727d5c8a6066df92f3ca5180f39ce667494a0f2a3'
CACHE_FILE = 'valuation_cache.json'
CACHE_DAYS = 7


def positive(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(str(value).replace(',', ''))
        return value if np.isfinite(value) and value > 0 else None
    except (ValueError, TypeError):
        return None


def normalize_holdings(payload):
    if not isinstance(payload.get('holdings'), list) or not payload.get('asof'):
        raise ValueError('Invalid K-ETF holdings response')
    holdings = []
    excluded = {'cash', 'future', 'futures', 'swap', 'bond', 'etf', 'fund', 'option', 'derivative'}
    for row in payload['holdings']:
        instrument = str(row.get('instrument_type', '')).lower()
        asset = str(row.get('asset_type', '')).lower()
        if instrument in excluded or asset in excluded:
            continue
        if instrument != 'stock' and asset != 'equity':
            continue
        weight = safe_round(row.get('weight'), 10)
        if weight is None or not 0 <= weight <= 100:
            continue
        holdings.append({'isin': row.get('holding_isin'), 'name': row.get('holding_name') or '-',
                         'weight_pct': weight, 'instrument_type': instrument, 'asset_type': asset})
    return {'as_of': str(payload['asof'])[:10],
            'holdings': sorted(holdings, key=lambda h: h['weight_pct'], reverse=True)[:10]}


def empty_ratio():
    return {'value': None, 'basis': None, 'period': None, 'is_consensus': None}


def parse_naver_valuation(payload):
    info = payload['financeInfo']
    periods = sorted(info['trTitleList'],
                     key=lambda p: (p.get('isConsensus') == 'Y', str(p['key'])), reverse=True)
    result = {key: empty_ratio() for key in ('per', 'pbr')}
    for metric in result:
        row = next((r for r in info['rowList'] if re.match(r'^' + metric + r'(?:\b|\()', str(r.get('title', '')), re.I)), None)
        if row is None:
            continue
        for period in periods:
            cell = row.get('columns', {}).get(str(period['key']), {})
            value = positive(cell.get('value') if isinstance(cell, dict) else cell)
            if value is not None:
                consensus = period.get('isConsensus') == 'Y'
                result[metric] = {'value': value, 'period': period.get('title') or str(period['key']),
                                  'basis': 'consensus' if consensus else 'actual', 'is_consensus': consensus}
                break
    return result


def parse_naver_foreign_valuation(payload):
    def period_date(period):
        # Sort by the displayed date, never by symbolic keys such as last12month.
        for field in ('title', 'key'):
            match = re.search(r'((?:19|20)\d{2})[./-]?(\d{2})(?:[./-]?(\d{2}))?',
                              str(period.get(field, '')))
            if match:
                return tuple(int(part or 0) for part in match.groups())
        return (0, 0, 0)

    periods = sorted(payload['trTitleList'], key=period_date, reverse=True)
    result = {key: empty_ratio() for key in ('per', 'pbr')}
    for metric in result:
        row = next((r for r in payload['rowList'] if r.get('title') == metric.upper()), None)
        if row is None:
            continue
        for period in periods:
            if period_date(period) == (0, 0, 0):
                continue
            cell = row.get('columns', {}).get(str(period['key']), {})
            value = positive(cell.get('value') if isinstance(cell, dict) else cell)
            if value is not None:
                result[metric] = {'value': value, 'basis': 'actual',
                                  'period': period.get('title') or str(period['key']),
                                  'is_consensus': False}
                break
    return result


def select_naver_foreign_stock(payload, name, isin=None, isin_lookup=None):
    candidates = [item for item in payload['result']['items']
                  if item.get('category') == 'stock' and item.get('reutersCode')
                  and item.get('nationCode') not in ('KOR', 'KR', 'Korea')
                  and not item['reutersCode'].endswith(('.KS', '.KQ'))]
    exact = [item for item in candidates if item.get('name') == name]
    matches = exact or candidates
    if len(matches) == 1:
        return matches[0]
    if isin and isin_lookup:
        isin_matches = []
        for item in matches:
            try:
                if isin_lookup(item).get('isinCode') == isin:
                    isin_matches.append(item)
            except Exception:
                continue
        if len(isin_matches) == 1:
            return isin_matches[0]
        country = {'US': 'USA', 'JP': 'JPN', 'CN': 'CHN', 'HK': 'HKG'}.get(isin[:2])
        primary = [item for item in isin_matches if item.get('nationCode') == country]
        if len(primary) == 1:
            return primary[0]
    raise ValueError(f'Ambiguous or missing foreign stock for {name}')


def parse_yahoo_valuation(info):
    result = {key: empty_ratio() for key in ('per', 'pbr')}
    for field, basis in [('forwardPE', 'forward'), ('trailingPE', 'trailing')]:
        value = positive(info.get(field))
        if value is not None:
            result['per'].update(value=value, basis=basis)
            break
    result['pbr'].update(value=positive(info.get('priceToBook')), basis='priceToBook')
    return result


def aggregate_multiple(holdings, metric, as_of):
    valid = [(positive(h.get('weight_pct')), positive(h.get(metric, {}).get('value')), h.get(metric, {}).get('basis')) for h in holdings]
    valid = [(w, v, b) for w, v, b in valid if w is not None and v is not None]
    covered = sum(w for w, _, _ in valid)
    return {'value': safe_round(covered / sum(w / v for w, v, _ in valid)) if valid else None,
            'valid_count': len(valid), 'top10_count': len(holdings),
            'covered_weight_pct': safe_round(covered),
            'top10_weight_pct': safe_round(sum(positive(h.get('weight_pct')) or 0 for h in holdings)),
            'basis': sorted({b for _, _, b in valid if b}), 'as_of': as_of}


def fetch_json(url, **kwargs):
    response = requests.get(url, timeout=15, **kwargs)
    response.raise_for_status()
    return response.json()


def fetch_valuation(isin, name=None):
    if re.fullmatch(r'KR[0-9A-Z]{10}', isin) and re.fullmatch(r'[0-9A-Z]{6}', isin[3:9]):
        symbol = isin[3:9]
        url = f'https://m.stock.naver.com/api/stock/{symbol}/finance/annual'
        result = parse_naver_valuation(fetch_json(url))
    else:
        if not name or name == '-':
            raise ValueError(f'Missing holding name for {isin}')
        search_url = 'https://stock.naver.com/api/autocomplete/search/autoComplete'
        params = {'query': name, 'target': 'stock'}
        search_payload = fetch_json(search_url, params=params)
        def lookup_isin(item):
            detail_url = f"https://stock.naver.com/api/foreign/{item['reutersCode']}/detail"
            return fetch_json(detail_url, params={'codeType': 'ETF'})
        quote = select_naver_foreign_stock(search_payload, name, isin, lookup_isin)
        symbol = quote['reutersCode']
        api_url = 'https://stock.naver.com/api/securityService/stock/finance/ratios/annual'
        result = parse_naver_foreign_valuation(fetch_json(api_url, params={'reutersCode': symbol}))
        if all(result[key]['value'] is None for key in ('per', 'pbr')):
            raise ValueError(f'No valid foreign PER/PBR for {name} ({symbol})')
        url = f'https://stock.naver.com/worldstock/stock/{symbol}/total'
        result['search_url'] = requests.Request('GET', search_url, params=params).prepare().url
        result['api_url'] = requests.Request('GET', api_url, params={'reutersCode': symbol}).prepare().url
    return {**result, 'symbol': symbol, 'url': url}


class ValuationCollector:
    def __init__(self, offline=False, path=CACHE_FILE):
        self.offline, self.path = offline, Path(path)
        self.now = datetime.now(timezone.utc)
        self.attempted = {}
        self.cache = {'holdings': {}, 'stocks': {}}
        if self.path.exists():
            try:
                self.cache.update(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError, OSError) as error:
                print(f'[WARN] Invalid valuation cache: {error}')

    def fresh(self, record):
        try:
            age = self.now - datetime.fromisoformat(record['retrieved_at'])
            return timedelta(0) <= age < timedelta(days=CACHE_DAYS)
        except (KeyError, ValueError, TypeError):
            return False

    def stock(self, isin, name=None):
        record = self.cache['stocks'].get(isin, {})
        if isin in self.attempted:
            return self.attempted[isin]
        if self.offline or self.fresh(record):
            return {**record, 'status': 'cached' if record else 'unavailable'}
        try:
            result = {**fetch_valuation(isin, name), 'retrieved_at': self.now.isoformat()}
            self.cache['stocks'][isin] = result
            self.attempted[isin] = {**result, 'status': 'live'}
            return self.attempted[isin]
        except Exception as error:
            print(f'[WARN] Valuation {isin}: {error}')
            # An online refresh failure must not silently use an old multiple.
            self.attempted[isin] = {'status': 'failed', 'error': str(error)}
            return self.attempted[isin]

    def enrich(self, ticker, facts):
        code = ticker.split('.')[0]
        url = f'https://www.k-etf.com/etf/{code}'
        api_url = f'https://anchor.k-etf.com/api/instrument/holdings/?code={code}&language=ko'
        record = self.cache['holdings'].get(code)
        status, error = 'cached' if record else 'unavailable', None
        if not self.offline:
            try:
                record = {**normalize_holdings(fetch_json(api_url, headers={'X-Internal-Api-Token': KETF_TOKEN})),
                          'retrieved_at': self.now.isoformat(), 'url': url, 'api_url': api_url}
                self.cache['holdings'][code] = record
                status = 'live'
            except Exception as exc:
                error = str(exc)
                print(f'[WARN] Holdings {code}: {exc}')
                status = 'cached_after_failure' if record else 'failed'
        if record is None and not self.offline and facts.get('holdings'):
            source = facts['sources'].get('holdings', {})
            record = {'holdings': facts['holdings'][:10], 'as_of': source.get('as_of'),
                      'url': source.get('url'), 'retrieved_at': None, 'provenance': 'verified_input'}
            self.cache['holdings'][code] = record
            status = 'verified_cached' if self.offline else 'verified_after_failure'
        record = record or {'holdings': [], 'as_of': None, 'url': url}
        source = {k: v for k, v in record.items() if k != 'holdings'}
        if record.get('provenance') == 'verified_input':
            status = 'verified_cached' if self.offline else 'verified_after_failure'
        source.update(status=status, error=error, k_etf_url=url)
        source['note'] = status + (', 보유자산 API 수집 실패' if error else '')
        facts['sources']['holdings'] = source
        holdings = []
        for raw in record['holdings']:
            h = dict(raw)
            valuation = self.stock(h['isin'], h.get('name')) if h.get('isin') else {'status': 'unavailable'}
            h.update(symbol=valuation.get('symbol'), per=valuation.get('per', empty_ratio()),
                     pbr=valuation.get('pbr', empty_ratio()), source=valuation)
            holdings.append(h)
        facts['holdings'] = holdings
        facts['holdings_summary'] = ', '.join(h['name'] for h in holdings[:3]) or None
        facts['top10_weight_pct'] = safe_round(
            sum(positive(h.get('weight_pct')) or 0 for h in holdings)
        ) if holdings else None
        facts['valuation'] = {key: aggregate_multiple(holdings, key, record['as_of']) for key in ('per', 'pbr')}

    def save(self):
        write_json_file(self.path, self.cache)


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
    collector = ValuationCollector(offline=args.offline)
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
        brief, detail = build_asset_outputs(name, ticker, df, market.get(ticker.split('.')[0]), now, optional.get(ticker), collector)
        result["etfs"].append(brief)
        details[ticker] = detail
    if failed and not (args.offline or args.allow_cache):
        raise SystemExit("Downloads failed; existing artifacts untouched. Use --allow-cache explicitly for partial history.")
    result["_meta"]["incomplete_history_count"] = len(failed)
    collector.save()
    remove_unregistered_detail_files()
    for ticker, detail in details.items():
        write_json_file(Path(DETAIL_DIR) / f"{ticker}.json", detail)
    write_json_file("trend_data.json", result)
    print(f"Generated {len(details)} ETFs; incomplete histories: {len(failed)}")


if __name__ == "__main__":
    main()
